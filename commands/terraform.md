# Terraform Command Reference

## Core Workflow

```
terraform init
terraform init -upgrade
terraform init -reconfigure
terraform plan
terraform plan -out=tfplan
terraform plan -var="key=value"
terraform plan -var-file="prod.tfvars"
terraform apply
terraform apply tfplan
terraform apply -auto-approve
terraform apply -var="key=value"
terraform destroy
terraform destroy -target=<resource>
terraform validate
terraform fmt
terraform fmt -recursive
```

## State Management

```
terraform state list
terraform state show <resource>
terraform state rm <resource>
terraform state mv <old-address> <new-address>
terraform state pull
terraform state push
terraform show
terraform show -json
terraform refresh
terraform import <resource-address> <resource-id>
```

## Workspaces

```
terraform workspace list
terraform workspace new <name>
terraform workspace select <name>
terraform workspace show
terraform workspace delete <name>
```

## Modules & Providers

```
terraform get
terraform get -update
terraform providers
terraform providers lock
terraform version
```

## Output & Variables

```
terraform output
terraform output <name>
terraform output -json
terraform console
```

## Debugging

```
terraform plan -detailed-exitcode
terraform apply -parallelism=1
TF_LOG=DEBUG terraform apply
terraform graph
terraform taint <resource>
terraform untaint <resource>
```

## Common .tf file structure (recognize these, not commands)

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "my-tf-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "web" {
  ami           = "ami-12345"
  instance_type = "t3.micro"
}

variable "instance_type" {
  default = "t3.micro"
}

output "instance_ip" {
  value = aws_instance.web.public_ip
}

data "aws_ami" "latest" {
  most_recent = true
}

module "vpc" {
  source = "./modules/vpc"
}
```

## Common gotchas worth knowing conceptually

- State file (`terraform.tfstate`) is the source of truth for what Terraform thinks exists — drift happens when someone changes infra outside Terraform (console, CLI) and the state no longer matches reality
- `terraform plan` before every `apply` — never skip this in shared environments
- Remote state (S3 + DynamoDB lock, or Terraform Cloud) is essential for team use — local state files cause conflicts
- `terraform destroy` is irreversible — always double check the plan output, especially `-target`

## Around and Beyond Terraform

```
tofu init        tofu plan        tofu apply              # OpenTofu: the open-source fork, same workflow
terragrunt run-all plan                                   # many root modules, shared config, in dependency order
terragrunt hclfmt
atlantis plan / atlantis apply                            # typed as pull-request comments

checkov -d . --framework terraform
checkov -d . --check CKV_AWS_20
trivy config .
terraform show -json plan.out > plan.json
conftest test plan.json --policy policy/
infracost breakdown --path .

packer init .        packer validate .        packer build .
packer build -var 'region=us-east-1' web.pkr.hcl

aws cloudformation describe-stacks --stack-name <name>
aws cloudformation describe-stack-events --stack-name <name> --max-items 10
aws cloudformation create-change-set --stack-name <name> --change-set-name <cs> --template-body file://t.yaml
aws cloudformation describe-change-set --stack-name <name> --change-set-name <cs>
aws cloudformation detect-stack-drift --stack-name <name>
aws cloudformation continue-update-rollback --stack-name <name> --resources-to-skip <LogicalId>
pulumi preview       pulumi up       pulumi stack ls
az deployment group what-if -g <rg> -f main.bicep
kubectl get managed          kubectl get claim -A           # Crossplane
```
