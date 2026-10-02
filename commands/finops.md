# FinOps Command Reference

Source material for `scenarios/finops/`. FinOps is the practice of making
cloud cost visible to the engineers who cause it, and treating it like
any other operational metric. The AWS category has one tutorial on
finding waste; this file goes further: allocation, forecasting,
rightsizing, commitments, Kubernetes cost, and the bills that surprise
people. AWS is the main example; the ideas are the same on every cloud.

## Reading the Bill

```
aws ce get-cost-and-usage --time-period Start=2026-09-01,End=2026-10-01 --granularity MONTHLY \
    --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE
aws ce get-cost-and-usage --time-period Start=2026-09-01,End=2026-10-01 --granularity MONTHLY \
    --metrics UnblendedCost --group-by Type=TAG,Key=team
aws ce get-cost-and-usage --time-period Start=2026-09-01,End=2026-10-01 --granularity DAILY \
    --metrics UnblendedCost --filter file://filter.json
aws ce get-cost-forecast --time-period Start=2026-10-02,End=2026-11-01 --metric UNBLENDED_COST --granularity MONTHLY
aws ce get-dimension-values --dimension USAGE_TYPE --time-period Start=2026-09-01,End=2026-10-01
```

## Tags, Budgets, and Anomalies

```
aws resourcegroupstaggingapi get-resources --resource-type-filters ec2:instance --query 'ResourceTagMappingList[?!(Tags[?Key==`team`])].ResourceARN'
aws ec2 create-tags --resources <id> --tags Key=team,Value=payments Key=env,Value=prod
aws ce list-cost-allocation-tags --status Active
aws budgets describe-budgets --account-id <account>
aws ce get-anomalies --date-interval StartDate=2026-09-20,EndDate=2026-10-01
```

## Waste and Rightsizing

```
aws compute-optimizer get-ec2-instance-recommendations --query 'instanceRecommendations[].[instanceArn,finding,currentInstanceType,recommendationOptions[0].instanceType]' --output table
aws ec2 describe-volumes --filters Name=status,Values=available
aws ec2 describe-snapshots --owner-ids self --query 'Snapshots[?StartTime<=`2025-10-01`].[SnapshotId,VolumeSize,StartTime]' --output table
aws elbv2 describe-target-health --target-group-arn <arn>
aws ec2 describe-instances --filters Name=instance-state-name,Values=running --query 'Reservations[].Instances[].[InstanceId,InstanceType,LaunchTime,Tags[?Key==`Name`]|[0].Value]' --output table
```

## Commitments and Spot

```
aws ce get-savings-plans-coverage --time-period Start=2026-09-01,End=2026-10-01
aws ce get-savings-plans-utilization --time-period Start=2026-09-01,End=2026-10-01
aws ce get-savings-plans-purchase-recommendation --savings-plans-type COMPUTE_SP --term-in-years ONE_YEAR --payment-option NO_UPFRONT --lookback-period-in-days THIRTY_DAYS
aws ec2 describe-spot-price-history --instance-types m7g.xlarge --product-descriptions "Linux/UNIX" --max-items 5
```

## Kubernetes Cost

```
kubectl cost namespace --window 7d --show-efficiency
kubectl cost deployment --window 7d -n <ns>
kubectl top pods -n <ns> --containers
kubectl get pods -n <ns> -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory
```

## Storage, Logs, and Data Transfer

```
aws s3api get-bucket-lifecycle-configuration --bucket <bucket>
aws s3api list-multipart-uploads --bucket <bucket>
aws logs describe-log-groups --query 'logGroups[?!retentionInDays].[logGroupName,storedBytes]' --output table
aws logs put-retention-policy --log-group-name <name> --retention-in-days 30
aws ec2 describe-nat-gateways --query 'NatGateways[].[NatGatewayId,SubnetId,State]' --output table
```
