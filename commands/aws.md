# AWS CLI Command Reference (DevOps-Relevant)

Source material for `scenarios/aws/`. Syntax is AWS CLI v2.

## Identity, Profiles & Regions

```
aws configure
aws configure --profile <name>
aws configure list
aws configure list-profiles
aws sts get-caller-identity
aws sts get-caller-identity --profile <name>
aws sso login --profile <name>
export AWS_PROFILE=<name>
export AWS_REGION=<region>
aws ec2 describe-regions --query 'Regions[].RegionName' --output text
```

## Output & Filtering (works on every command)

```
--output json | table | text | yaml
--query '<JMESPath>'
--filters Name=<field>,Values=<v1>,<v2>
--region <region>
--no-cli-pager
```

## EC2 Instances

```
aws ec2 describe-instances
aws ec2 describe-instances --instance-ids <i-id>
aws ec2 describe-instances --filters Name=tag:Name,Values=<name>
aws ec2 describe-instances --filters Name=instance-state-name,Values=running
aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,State.Name,PrivateIpAddress,PublicIpAddress]' --output table
aws ec2 run-instances --image-id <ami> --instance-type <type> --subnet-id <subnet> --security-group-ids <sg> --key-name <key>
aws ec2 start-instances --instance-ids <i-id>
aws ec2 stop-instances --instance-ids <i-id>
aws ec2 reboot-instances --instance-ids <i-id>
aws ec2 terminate-instances --instance-ids <i-id>
aws ec2 describe-instance-status --instance-ids <i-id>
aws ec2 get-console-output --instance-id <i-id> --latest --output text
aws ec2 modify-instance-attribute --instance-id <i-id> --instance-type <type>
aws ec2 describe-images --owners amazon --filters Name=name,Values=<pattern>
aws ec2 create-tags --resources <id> --tags Key=<k>,Value=<v>
```

## Connecting to Instances

```
aws ssm start-session --target <i-id>
aws ssm describe-instance-information
aws ssm send-command --document-name AWS-RunShellScript --targets Key=tag:<k>,Values=<v> --parameters commands=<cmd>
aws ssm list-command-invocations --command-id <id> --details
aws ec2-instance-connect ssh --instance-id <i-id>
ssh -i <key.pem> ec2-user@<public-ip>
```

## VPC Networking

```
aws ec2 describe-vpcs
aws ec2 describe-subnets --filters Name=vpc-id,Values=<vpc-id>
aws ec2 describe-route-tables --filters Name=vpc-id,Values=<vpc-id>
aws ec2 describe-route-tables --filters Name=association.subnet-id,Values=<subnet-id>
aws ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values=<vpc-id>
aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=<vpc-id>
aws ec2 create-route --route-table-id <rtb> --destination-cidr-block 0.0.0.0/0 --gateway-id <igw>
aws ec2 create-route --route-table-id <rtb> --destination-cidr-block 0.0.0.0/0 --nat-gateway-id <nat>
aws ec2 associate-route-table --route-table-id <rtb> --subnet-id <subnet>
aws ec2 allocate-address
aws ec2 associate-address --instance-id <i-id> --allocation-id <eipalloc>
aws ec2 describe-vpc-endpoints
aws ec2 describe-vpc-peering-connections
aws ec2 describe-flow-logs
```

## Security Groups & NACLs

```
aws ec2 describe-security-groups --group-ids <sg>
aws ec2 describe-security-groups --filters Name=ip-permission.cidr,Values=0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id <sg> --protocol tcp --port <port> --cidr <cidr>
aws ec2 authorize-security-group-ingress --group-id <sg> --protocol tcp --port <port> --source-group <sg>
aws ec2 revoke-security-group-ingress --group-id <sg> --protocol tcp --port <port> --cidr <cidr>
aws ec2 describe-network-acls --filters Name=association.subnet-id,Values=<subnet-id>
aws ec2 replace-network-acl-entry --network-acl-id <acl> --rule-number <n> --protocol tcp --port-range From=<a>,To=<b> --cidr-block <cidr> --rule-action allow --egress|--ingress
aws ec2 describe-network-interfaces --filters Name=attachment.instance-id,Values=<i-id>
```

## IAM

```
aws iam list-users
aws iam list-roles --query 'Roles[].RoleName'
aws iam get-role --role-name <role>
aws iam list-attached-role-policies --role-name <role>
aws iam list-role-policies --role-name <role>
aws iam get-policy-version --policy-arn <arn> --version-id <v>
aws iam create-role --role-name <role> --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name <role> --policy-arn <arn>
aws iam simulate-principal-policy --policy-source-arn <arn> --action-names <action> --resource-arns <arn>
aws iam list-access-keys --user-name <user>
aws iam update-access-key --user-name <user> --access-key-id <key> --status Inactive
aws iam delete-access-key --user-name <user> --access-key-id <key>
aws sts assume-role --role-arn <arn> --role-session-name <name>
aws sts decode-authorization-message --encoded-message <msg>
aws iam get-account-authorization-details
aws organizations list-policies --filter SERVICE_CONTROL_POLICY
```

## S3

```
aws s3 ls
aws s3 ls s3://<bucket>/<prefix>/ --recursive --human-readable --summarize
aws s3 cp <file> s3://<bucket>/<key>
aws s3 sync <dir> s3://<bucket>/<prefix> --delete
aws s3 rm s3://<bucket>/<key>
aws s3 presign s3://<bucket>/<key> --expires-in 3600
aws s3api get-bucket-policy --bucket <bucket>
aws s3api get-public-access-block --bucket <bucket>
aws s3api put-public-access-block --bucket <bucket> --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api get-bucket-encryption --bucket <bucket>
aws s3api get-bucket-versioning --bucket <bucket>
aws s3api put-bucket-versioning --bucket <bucket> --versioning-configuration Status=Enabled
```

## CloudWatch & Logs

```
aws logs describe-log-groups
aws logs tail <group> --follow --since 10m
aws logs tail <group> --filter-pattern "ERROR"
aws logs start-query --log-group-name <group> --start-time <t> --end-time <t> --query-string '<insights query>'
aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=InstanceId,Value=<i-id> --start-time <t> --end-time <t> --period 300 --statistics Average
aws cloudwatch describe-alarms --state-value ALARM
aws cloudwatch put-metric-alarm ...
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=<name>
```

## Load Balancing & Auto Scaling

```
aws elbv2 describe-load-balancers
aws elbv2 describe-target-groups --load-balancer-arn <arn>
aws elbv2 describe-target-health --target-group-arn <arn>
aws elbv2 modify-target-group --target-group-arn <arn> --health-check-path <path>
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names <asg>
aws autoscaling set-desired-capacity --auto-scaling-group-name <asg> --desired-capacity <n>
aws autoscaling start-instance-refresh --auto-scaling-group-name <asg>
aws autoscaling describe-scaling-activities --auto-scaling-group-name <asg>
```

## Containers (EKS / ECR / ECS)

```
aws eks list-clusters
aws eks update-kubeconfig --name <cluster> --region <region>
aws eks describe-cluster --name <cluster>
aws ecr get-login-password | docker login --username AWS --password-stdin <acct>.dkr.ecr.<region>.amazonaws.com
aws ecr describe-images --repository-name <repo>
aws ecs list-services --cluster <cluster>
aws ecs describe-services --cluster <cluster> --services <svc>
aws ecs update-service --cluster <cluster> --service <svc> --force-new-deployment
```

## Cost & Governance

```
aws ce get-cost-and-usage --time-period Start=<d>,End=<d> --granularity MONTHLY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE
aws resourcegroupstaggingapi get-resources --tag-filters Key=<k>,Values=<v>
aws ec2 describe-volumes --filters Name=status,Values=available
aws ec2 describe-addresses --query 'Addresses[?AssociationId==null]'
aws guardduty list-findings --detector-id <id>
aws securityhub get-findings --filters '{"SeverityLabel":[{"Value":"CRITICAL","Comparison":"EQUALS"}]}'
```
