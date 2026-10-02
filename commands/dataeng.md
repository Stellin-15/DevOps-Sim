# Data Engineering Command Reference

Source material for `scenarios/dataeng/`. Data pipelines are production
systems that platform engineers end up running: schedulers, transform
jobs, warehouses, and the streams that feed them. MLOps covers
*operating* Airflow for model training; Databases and Messaging cover
PostgreSQL and Kafka themselves. This file is the data platform's own
tools.

## Airflow: Writing and Testing DAGs

```
python dags/<file>.py                          # does the DAG file even import?
airflow dags list-import-errors
airflow tasks list <dag_id> --tree
airflow dags test <dag_id> <logical_date>      # run the whole DAG once, locally
airflow tasks test <dag_id> <task_id> <logical_date>
airflow dags show <dag_id>
airflow dags backfill -s <start> -e <end> <dag_id>
```

## dbt

```
dbt debug                         # connection and project check
dbt deps
dbt run --select <model>          dbt run --select <model>+        # model and everything downstream
dbt test --select <model>
dbt build                         # run + test, in dependency order
dbt build --select state:modified+ --state ./prod-artifacts
dbt ls --select <model>+
dbt docs generate
dbt source freshness
```

## Warehouses

```
bq ls <dataset>                   bq show --schema --format=prettyjson <dataset>.<table>
bq query --dry_run --use_legacy_sql=false '<sql>'
bq query --use_legacy_sql=false --maximum_bytes_billed=10000000000 '<sql>'
bq show --format=prettyjson <dataset>.<table> | jq '.timePartitioning, .clustering'
snowsql -q "SHOW WAREHOUSES"
snowsql -q "ALTER WAREHOUSE <wh> SET AUTO_SUSPEND = 60"
```

## Spark on Kubernetes

```
spark-submit --master k8s://https://<api-server> --deploy-mode cluster --name <job> \
    --conf spark.kubernetes.container.image=<image> --conf spark.executor.instances=4 local:///opt/app/job.py
kubectl get pods -n <ns> -l spark-role=driver
kubectl get pods -n <ns> -l spark-role=executor
kubectl logs -n <ns> <driver-pod> --tail=50
kubectl port-forward -n <ns> <driver-pod> 4040:4040        # the Spark UI
kubectl get sparkapplications -n <ns>                     # with the Spark Operator
```

## Change Data Capture (Debezium on Kafka Connect)

```
curl -s $CONNECT/connectors | jq
curl -s $CONNECT/connectors/<name>/status | jq
curl -s -X POST $CONNECT/connectors/<name>/tasks/0/restart
curl -s -X PUT $CONNECT/connectors/<name>/pause
curl -s $CONNECT/connectors/<name>/config | jq
```
