# Serverless and Managed Compute Command Reference

Source material for `scenarios/serverless/`. "Serverless" here means
compute you don't patch or scale yourself: functions (AWS Lambda, Cloud
Functions, Azure Functions) and containers run for you (ECS on Fargate,
Cloud Run, Container Apps). The servers still exist; the limits you hit
are different ones: concurrency, timeouts, cold starts, and event
retries. AWS is the main example.

## Lambda: Inspect and Invoke

```
aws lambda list-functions --query 'Functions[].[FunctionName,Runtime,MemorySize,Timeout]' --output table
aws lambda get-function-configuration --function-name <fn>
aws lambda invoke --function-name <fn> --payload file://event.json --cli-binary-format raw-in-base64-out out.json
aws logs tail /aws/lambda/<fn> --follow
aws logs tail /aws/lambda/<fn> --since 15m --filter-pattern "ERROR"
aws lambda update-function-configuration --function-name <fn> --memory-size 1024 --timeout 30
```

Every invocation ends with a REPORT line: Duration, Billed Duration,
Memory Size, Max Memory Used, and Init Duration on a cold start.

## Lambda: Concurrency

```
aws lambda get-account-settings
aws lambda get-function-concurrency --function-name <fn>
aws lambda put-function-concurrency --function-name <fn> --reserved-concurrent-executions 100
aws lambda delete-function-concurrency --function-name <fn>
aws lambda put-provisioned-concurrency-config --function-name <fn> --qualifier <alias> --provisioned-concurrent-executions 10
```

## Lambda: Versions, Aliases, Deploys

```
aws lambda update-function-code --function-name <fn> --image-uri <uri>
aws lambda publish-version --function-name <fn>
aws lambda list-versions-by-function --function-name <fn>
aws lambda get-alias --function-name <fn> --name live
aws lambda update-alias --function-name <fn> --name live --function-version 12
aws lambda update-alias --function-name <fn> --name live --function-version 12 --routing-config 'AdditionalVersionWeights={"13"=0.1}'
```

## Lambda: Events and Failures

```
aws lambda list-event-source-mappings --function-name <fn>
aws lambda update-event-source-mapping --uuid <uuid> --batch-size 10
aws lambda get-function-event-invoke-config --function-name <fn>
aws lambda put-function-event-invoke-config --function-name <fn> --maximum-retry-attempts 1 --destination-config '{"OnFailure":{"Destination":"<arn>"}}'
aws s3api get-bucket-notification-configuration --bucket <bucket>
```

Synchronous callers get the error. Asynchronous events are retried twice,
then dropped unless a dead-letter queue or failure destination is set.
Queue and stream sources retry until the message expires.

## API Gateway

```
aws apigatewayv2 get-apis
aws apigatewayv2 get-routes --api-id <id>
aws apigatewayv2 get-integrations --api-id <id>
aws apigatewayv2 get-stage --api-id <id> --stage-name prod
curl -s -o /dev/null -w "%{http_code} %{time_total}\n" https://<id>.execute-api.<region>.amazonaws.com/<path>
```

## ECS on Fargate

```
aws ecs list-services --cluster <cluster>
aws ecs describe-services --cluster <cluster> --services <svc> --query 'services[0].events[:5]'
aws ecs list-tasks --cluster <cluster> --service-name <svc> --desired-status STOPPED
aws ecs describe-tasks --cluster <cluster> --tasks <task> --query 'tasks[0].[stoppedReason,containers[0].reason]'
aws ecs update-service --cluster <cluster> --service <svc> --force-new-deployment
aws ecs update-service --cluster <cluster> --service <svc> --health-check-grace-period-seconds 180
aws ecs execute-command --cluster <cluster> --task <task> --container <name> --interactive --command "/bin/sh"
```

## Cloud Run and Azure Functions

```
gcloud run services list
gcloud run services describe <svc> --region <region>
gcloud run revisions list --service <svc> --region <region>
gcloud run services update-traffic <svc> --region <region> --to-revisions <rev>=100
gcloud run services logs read <svc> --region <region> --limit 20
gcloud run deploy <svc> --image <image> --region <region> --no-traffic
az functionapp list -o table
az functionapp show -g <rg> -n <app> --query state
az functionapp log tail -g <rg> -n <app>
```
