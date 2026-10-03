"""Tests for db_sandbox.py: each seeded problem is visible through real SQL,
each real fix clears it, the classic wrong fixes don't, transactions are
honoured, and saved states reload from their dump."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import db_sandbox as db
from sandbox_common import run_command


def fresh(*problems, seed=7):
    return db.generate_state(seed=seed, problems=list(problems))


def run(state, cmd):
    return run_command(db.handle_command, state, cmd)


# ---------------------------------------------------------------- generation

def test_random_state_has_two_problems():
    for seed in range(30):
        state = db.generate_state(seed=seed)
        assert len(state["problems"]) == 2 and set(state["problems"]) <= set(db.PROBLEMS)


def test_generation_is_deterministic_per_seed():
    a, b = fresh("orphaned_items", seed=3), fresh("orphaned_items", seed=3)
    assert a["dump"] == b["dump"]


def test_clean_state_passes_every_check():
    state = fresh()
    for check in ("query_uses_index", "no_duplicates", "no_orphans", "committed"):
        assert db.GOAL_CHECKS[check](state, {}), check


def test_state_is_json_saveable_and_reloads():
    state = fresh("duplicate_load")
    run(state, "DELETE FROM daily_sales WHERE rowid NOT IN (SELECT min(rowid) FROM daily_sales GROUP BY order_id)")
    reloaded = json.loads(json.dumps(state))
    assert db.GOAL_CHECKS["no_duplicates"](reloaded, {})


# ------------------------------------------------------------------ commands

def test_meta_commands():
    state = fresh()
    assert "daily_sales" in run(state, ".tables")
    assert "idx_orders_customer_id" in run(state, ".indexes orders")
    assert "CREATE TABLE orders" in run(state, ".schema orders")
    assert 'Table "orders"' in run(state, "\\d orders")
    assert "customers" in run(state, "\\dt")


def test_select_renders_rows_and_count():
    out = run(fresh(), "SELECT id, status FROM orders ORDER BY id LIMIT 2;")
    assert out.splitlines()[0].split() == ["id", "status"] and out.endswith("(2 rows)")


def test_long_results_are_truncated():
    assert "showing 40" in run(fresh(), "SELECT id FROM orders")


def test_sql_errors_are_reported_not_raised():
    assert run(fresh(), "SELEC 1").startswith("Error:")
    assert "no such table" in run(fresh(), "SELECT * FROM nope")


def test_concatenation_survives_pipes():
    assert "ab" in run(fresh(), "SELECT 'a' || 'b' AS x | grep ab")


def test_postgres_explain_is_redirected():
    assert "EXPLAIN QUERY PLAN" in run(fresh(), "EXPLAIN ANALYZE SELECT 1")


def test_file_access_is_blocked():
    assert "not allowed" in run(fresh(), "ATTACH DATABASE 'x.db' AS x")


def test_write_verbs_report_counts():
    state = fresh()
    assert run(state, "UPDATE products SET stock = stock WHERE id <= 3") == "UPDATE 3"
    assert run(state, "CREATE UNIQUE INDEX uq_x ON products(name)") == "CREATE INDEX"


# --------------------------------------------------------------- transactions

def test_rollback_undoes_and_costs_no_collateral():
    state = fresh()
    baseline = db.collateral_issues(state)
    run(state, "BEGIN")
    run(state, "DELETE FROM customers")
    assert db.collateral_issues(state) == baseline
    assert not db.GOAL_CHECKS["committed"](state, {})
    run(state, "ROLLBACK")
    assert db.collateral_issues(state) == baseline
    assert "150" in run(state, "SELECT count(*) FROM customers")


def test_uncommitted_work_is_not_saved():
    state = fresh()
    run(state, "BEGIN")
    run(state, "DELETE FROM products")
    reloaded = json.loads(json.dumps(state))
    assert "20" in run(reloaded, "SELECT count(*) FROM products")


def test_committed_damage_is_collateral():
    state = fresh()
    run(state, "DELETE FROM orders WHERE id < 10")
    assert "deleted real orders" in db.collateral_issues(state)


# ------------------------------------------------------------------- problems

def test_missing_index_scan_then_search():
    state = fresh("missing_index")
    plan = run(state, "EXPLAIN QUERY PLAN " + db.MY_ORDERS_SQL)
    assert "SCAN orders" in plan  # an index scan on created_at is still a scan
    assert not db.GOAL_CHECKS["query_uses_index"](state, {})
    assert "DROP INDEX idx_orders_customer_id" in run(state, "SELECT * FROM schema_migrations")
    run(state, "CREATE INDEX idx_orders_customer_id ON orders(customer_id)")
    assert db.GOAL_CHECKS["query_uses_index"](state, {})


def test_duplicate_load_needs_dedupe_and_guard():
    state = fresh("duplicate_load")
    assert "manual re-run" in run(state, "SELECT * FROM job_runs WHERE run_for = '2026-10-01'")
    assert "UNIQUE constraint failed" in run(state, "CREATE UNIQUE INDEX uq ON daily_sales(order_id)")
    run(state, "DELETE FROM daily_sales WHERE rowid NOT IN (SELECT min(rowid) FROM daily_sales GROUP BY order_id)")
    assert db.GOAL_CHECKS["no_duplicates"](state, {}) and not db.GOAL_CHECKS["unique_guard"](state, {})
    run(state, "CREATE UNIQUE INDEX uq ON daily_sales(order_id)")
    assert db.GOAL_CHECKS["unique_guard"](state, {})


def test_guard_on_loaded_at_does_not_count():
    state = fresh()
    run(state, "CREATE UNIQUE INDEX uq ON daily_sales(order_id, loaded_at)")
    assert not db.GOAL_CHECKS["unique_guard"](state, {})


def test_deleting_the_whole_day_is_collateral():
    state = fresh("duplicate_load")
    run(state, "DELETE FROM daily_sales WHERE sale_date = '2026-10-01'")
    assert not db.GOAL_CHECKS["no_duplicates"](state, {})
    assert any("daily_sales" in i for i in db.collateral_issues(state))


def test_orphans_found_and_removed():
    state = fresh("orphaned_items")
    out = run(state, "SELECT count(*) FROM order_items WHERE order_id NOT IN (SELECT id FROM orders)")
    assert out.splitlines()[1].strip() != "0"
    assert "0" in run(state, "PRAGMA foreign_keys")
    run(state, "DELETE FROM order_items WHERE order_id NOT IN (SELECT id FROM orders)")
    assert db.GOAL_CHECKS["no_orphans"](state, {})
    assert db.collateral_issues(state) == set()


@pytest.mark.parametrize("fix, restored", [
    ("INSERT OR IGNORE INTO addresses SELECT * FROM addresses_backup_20261002", True),
    ("INSERT INTO addresses SELECT * FROM addresses_backup_20261002 b "
     "WHERE NOT EXISTS (SELECT 1 FROM addresses a WHERE a.id = b.id)", True),
    # replaces today's edit with last night's value
    ("INSERT OR REPLACE INTO addresses SELECT * FROM addresses_backup_20261002", False),
    # fails on the first existing id, so nothing is inserted
    ("INSERT INTO addresses SELECT * FROM addresses_backup_20261002", False),
])
def test_address_restore(fix, restored):
    state = fresh("deleted_addresses")
    run(state, fix)
    assert db.GOAL_CHECKS["addresses_restored"](state, {}) is restored


def test_restoring_by_swapping_tables_loses_todays_rows():
    state = fresh("deleted_addresses")
    run(state, "DROP TABLE addresses")
    run(state, "ALTER TABLE addresses_backup_20261002 RENAME TO addresses")
    assert not db.GOAL_CHECKS["addresses_restored"](state, {})
    assert "deleted the addresses customers added today" in db.collateral_issues(state)


def test_check_command_reports_each_problem():
    state = fresh("missing_index", "orphaned_items")
    assert run(state, "check").count("[open ]") == 2
    run(state, "CREATE INDEX i ON orders(customer_id)")
    assert run(state, "check").count("[fixed]") == 1
