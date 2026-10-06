"""Tests for tf_sandbox.py: plan really compares code, state, and the real
account, and each seeded problem shows up in it the way it would in real
Terraform."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import tf_sandbox as tf
from sandbox_common import run_command


def fresh(*problems, seed=3):
    return tf.generate_state(seed=seed, problems=list(problems))


def run(state, cmd):
    return run_command(tf.handle_command, state, cmd)


def actions(state):
    return [(a, addr) for a, addr, _ in tf.compute_plan(state)["changes"]]


# ---------------------------------------------------------------- generation

def test_random_state_has_two_problems():
    for seed in range(40):
        s = tf.generate_state(seed=seed)
        assert len(s["problems"]) == 2 and set(s["problems"]) <= set(tf.PROBLEMS)


def test_state_is_json_saveable_and_deterministic():
    a, b = fresh("drift", seed=9), fresh("drift", seed=9)
    assert json.dumps(a) == json.dumps(b)


def test_clean_stack_plans_no_changes():
    out = run(fresh(), "terraform plan")
    assert "No changes. Your infrastructure matches the configuration." in out


# ---------------------------------------------------------------------- plan

def test_drift_is_an_in_place_update_back_to_the_code():
    s = fresh("drift")
    assert actions(s) == [("update", "aws_security_group.web")]
    out = run(s, "terraform plan")
    assert "Objects have changed outside of Terraform" in out
    assert "[80, 443, 22] -> [80, 443]" in out and "0 to add, 1 to change, 0 to destroy" in out


def test_refresh_only_plan_reports_drift_without_actions():
    out = run(fresh("drift"), "terraform plan -refresh-only")
    assert "refresh-only plan" in out and "Terraform will perform" not in out


def test_rename_plans_destroy_and_create():
    assert sorted(actions(fresh("renamed"))) == [("create", "aws_instance.app"), ("destroy", "aws_instance.web")]


def test_unmanaged_bucket_plans_a_create():
    assert actions(fresh("unmanaged_bucket")) == [("create", "aws_s3_bucket.assets")]


def test_handed_over_database_plans_a_destroy():
    s = fresh("handed_over")
    assert actions(s) == [("destroy", "aws_db_instance.reports")]
    assert "because it is not in configuration" in run(s, "terraform plan")


def test_force_new_attribute_means_replacement():
    s = fresh()
    s["config"]["aws_instance.web"]["attrs"]["ami"] = "ami-0new"
    assert actions(s) == [("replace", "aws_instance.web")]
    assert "forces replacement" in run(s, "terraform plan")


def test_object_deleted_outside_is_recreated():
    s = fresh()
    del s["real"]["shop-logs-prod"]
    assert actions(s) == [("create", "aws_s3_bucket.logs")]
    assert "no longer exists" in run(s, "terraform plan")


def test_lock_blocks_plan_unless_lock_false():
    s = fresh("stale_lock")
    out = run(s, "terraform plan")
    assert "Error acquiring the state lock" in out and s["lock"]["id"] in out and "ci-runner-7" in out
    assert "No changes" in run(s, "terraform plan -lock=false")


# --------------------------------------------------------------------- views

def test_state_list_and_show():
    s = fresh("handed_over")
    assert "aws_db_instance.reports" in run(s, "terraform state list")
    assert 'identifier     = "shop-reports"' in run(s, "terraform state show aws_db_instance.reports")
    assert "No instance found" in run(s, "terraform state show aws_instance.nope")


def test_state_pull_is_json():
    data = json.loads(run(fresh(), "terraform state pull"))
    assert data["version"] == 4 and len(data["resources"]) == 5


def test_config_shows_the_code():
    assert 'resource "aws_instance" "app"' in run(fresh("renamed"), "cat main.tf")


def test_pipes_and_unknown_commands():
    assert run(fresh(), "terraform state list | grep aws_instance") == "aws_instance.web"
    assert "not simulated" in run(fresh(), "terraform taint aws_vpc.main")
    assert "isn't available" in run(fresh(), "terraform destroy")


# ------------------------------------------------------------- state surgery

def test_state_mv_fixes_a_rename_without_touching_the_instance():
    s = fresh("renamed")
    web_id = s["tfstate"]["aws_instance.web"]["id"]
    out = run(s, "terraform state mv aws_instance.web aws_instance.app")
    assert "Successfully moved 1 object(s)" in out
    assert actions(s) == [] and s["tfstate"]["aws_instance.app"]["id"] == web_id


def test_state_mv_errors():
    s = fresh()
    assert "does not match anything" in run(s, "terraform state mv aws_instance.nope aws_instance.app")
    assert "already a resource" in run(s, "terraform state mv aws_vpc.main aws_vpc.main")
    assert "types don't match" in run(s, "terraform state mv aws_vpc.main aws_instance.vpc")


def test_state_rm_forgets_without_destroying():
    s = fresh("handed_over")
    out = run(s, "terraform state rm aws_db_instance.reports")
    assert "Successfully removed 1 resource instance(s)" in out
    assert actions(s) == [] and "shop-reports" in s["real"]


def test_state_rm_of_unknown_address():
    assert "No matching objects" in run(fresh(), "terraform state rm aws_db_instance.nope")


def test_state_surgery_respects_the_lock():
    s = fresh("stale_lock", "renamed")
    assert "Error acquiring the state lock" in run(s, "terraform state mv aws_instance.web aws_instance.app")
    assert "aws_instance.web" in s["tfstate"]
    run(s, "terraform state mv -lock=false aws_instance.web aws_instance.app")
    assert "aws_instance.app" in s["tfstate"] and s["lock_bypassed"]


# ------------------------------------------------------------------ apply

def test_apply_asks_first_and_changes_nothing():
    s = fresh("drift")
    out = run(s, "terraform apply")
    assert "Do you want to perform these actions?" in out and "-auto-approve" in out
    assert 22 in s["real"][s["tfstate"]["aws_security_group.web"]["id"]]["attrs"]["ingress_ports"]


def test_apply_reverts_drift():
    s = fresh("drift")
    out = run(s, "terraform apply -auto-approve")
    assert "1 changed" in out
    assert s["real"][s["tfstate"]["aws_security_group.web"]["id"]]["attrs"]["ingress_ports"] == [80, 443]
    assert actions(s) == []


def test_refresh_only_apply_accepts_drift_into_state():
    s = fresh("drift")
    run(s, "terraform apply -refresh-only -auto-approve")
    assert s["tfstate"]["aws_security_group.web"]["attrs"]["ingress_ports"] == [80, 443, 22]
    assert actions(s) == [("update", "aws_security_group.web")]  # the code still says otherwise


def test_applying_a_rename_replaces_the_real_instance():
    s = fresh("renamed")
    old = s["tfstate"]["aws_instance.web"]["id"]
    out = run(s, "terraform apply -auto-approve")
    assert "1 added, 0 changed, 1 destroyed" in out
    assert old not in s["real"] and s["tfstate"]["aws_instance.app"]["id"] != old


def test_applying_an_existing_bucket_fails():
    s = fresh("unmanaged_bucket")
    out = run(s, "terraform apply -auto-approve")
    assert "BucketAlreadyOwnedByYou" in out and "aws_s3_bucket.assets" not in s["tfstate"]


def test_applying_a_handed_over_database_destroys_it():
    s = fresh("handed_over")
    run(s, "terraform apply -auto-approve")
    assert "shop-reports" not in s["real"]


def test_apply_respects_the_lock():
    s = fresh("stale_lock", "drift")
    assert "Error acquiring the state lock" in run(s, "terraform apply -auto-approve")


# ----------------------------------------------------------------- import

def test_import_adopts_an_existing_bucket():
    s = fresh("unmanaged_bucket")
    assert "Import successful!" in run(s, "terraform import aws_s3_bucket.assets shop-assets-prod")
    assert actions(s) == []


def test_import_errors():
    s = fresh("unmanaged_bucket")
    assert "does not exist in the configuration" in run(s, "terraform import aws_s3_bucket.nope shop-assets-prod")
    assert "non-existent remote object" in run(s, "terraform import aws_s3_bucket.assets shop-assets-typo")
    assert "already managed" in run(s, "terraform import aws_s3_bucket.logs shop-logs-prod")


# ----------------------------------------------------------- force-unlock

def test_force_unlock_needs_the_right_id_and_confirmation():
    s = fresh("stale_lock")
    lock = s["lock"]["id"]
    assert "does not match" in run(s, "terraform force-unlock -force 00000000-0000-0000-0000-000000000000")
    assert "Do you really want to force-unlock?" in run(s, f"terraform force-unlock {lock}")
    assert s["lock"] is not None
    assert "successfully unlocked" in run(s, f"terraform force-unlock -force {lock}")
    assert s["lock"] is None and "No changes" in run(s, "terraform plan")


def test_force_unlock_without_a_lock():
    assert "no lock is held" in run(fresh(), "terraform force-unlock -force abc")
