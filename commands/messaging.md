# Messaging Command Reference

Source material for `scenarios/messaging/`. System Design explains why
you'd put a queue between two services. This file is about operating
one: Kafka first, then RabbitMQ and the cloud queues. The Kafka commands
are shown as `kafka-topics.sh` and so on; some distributions drop the
`.sh`. `$BS` stands for the bootstrap server list, for example
`kafka-0:9092`.

## Kafka: Topics and Partitions

```
kafka-topics.sh --bootstrap-server $BS --list
kafka-topics.sh --bootstrap-server $BS --describe --topic <topic>
kafka-topics.sh --bootstrap-server $BS --create --topic <topic> --partitions 6 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --alter --topic <topic> --partitions 12
kafka-topics.sh --bootstrap-server $BS --describe --under-replicated-partitions
kafka-configs.sh --bootstrap-server $BS --entity-type topics --entity-name <topic> --describe
kafka-configs.sh --bootstrap-server $BS --entity-type topics --entity-name <topic> --alter --add-config retention.ms=86400000
```

## Kafka: Reading and Writing by Hand

```
kafka-console-consumer.sh --bootstrap-server $BS --topic <topic> --from-beginning --max-messages 5
kafka-console-producer.sh --bootstrap-server $BS --topic <topic>
kcat -b $BS -L                                   # metadata: brokers, topics, leaders
kcat -b $BS -C -t <topic> -o -5 -e               # the last 5 messages
kcat -b $BS -C -t <topic> -p <partition> -o <offset> -c 1
kcat -b $BS -C -t <topic> -f '%p %o %k %s\n'     # partition, offset, key, value
```

## Kafka: Consumer Groups

```
kafka-consumer-groups.sh --bootstrap-server $BS --list
kafka-consumer-groups.sh --bootstrap-server $BS --describe --group <group>
kafka-consumer-groups.sh --bootstrap-server $BS --describe --group <group> --state
kafka-consumer-groups.sh --bootstrap-server $BS --describe --group <group> --members
kafka-consumer-groups.sh --bootstrap-server $BS --group <group> --topic <topic> --reset-offsets --to-latest --dry-run
kafka-consumer-groups.sh --bootstrap-server $BS --group <group> --topic <topic>:<partition> --reset-offsets --to-offset <n> --execute
```

Lag = log end offset minus the group's committed offset, per partition.

## Kafka: Brokers

```
kafka-broker-api-versions.sh --bootstrap-server $BS | grep id
kafka-metadata-quorum.sh --bootstrap-server $BS describe --status        # KRaft controllers
kafka-log-dirs.sh --bootstrap-server $BS --describe --topic-list <topic>
kafka-reassign-partitions.sh --bootstrap-server $BS --reassignment-json-file plan.json --execute
kafka-leader-election.sh --bootstrap-server $BS --election-type preferred --all-topic-partitions
```

Settings that decide durability: `replication.factor` (copies),
`min.insync.replicas` (copies that must acknowledge), producer `acks`
(`all` waits for the in-sync set).

## RabbitMQ

```
rabbitmq-diagnostics status
rabbitmq-diagnostics alarms
rabbitmqctl list_queues name messages consumers
rabbitmqctl list_connections name state
rabbitmqctl list_policies
rabbitmqctl set_policy <name> "<pattern>" '{"max-length":100000,"overflow":"reject-publish"}' --apply-to queues
rabbitmqctl purge_queue <queue>
rabbitmqadmin get queue=<queue> count=1
```

## Cloud Queues

```
aws sqs get-queue-attributes --queue-url <url> --attribute-names All
aws sqs receive-message --queue-url <url> --max-number-of-messages 1 --visibility-timeout 0
aws sqs set-queue-attributes --queue-url <url> --attributes VisibilityTimeout=120
aws sqs start-message-move-task --source-arn <dlq-arn>          # redrive from a dead-letter queue
aws sns list-subscriptions-by-topic --topic-arn <arn>
gcloud pubsub subscriptions describe <sub>
gcloud pubsub subscriptions pull <sub> --limit=1
gcloud pubsub subscriptions seek <sub> --time=<timestamp>
```
