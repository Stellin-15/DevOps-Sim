# System Design Reference

Source material for `scenarios/systemdesign/`. System design is mostly
judgment, so this category mixes two kinds of step: real commands that
show a building block working (or failing), and multiple-choice design
decisions answered with a letter. Design documents are practised in the
Writing Labs.

## Estimation Cheat Sheet

```
1 day  = 86,400 seconds   (~100,000 for quick maths)
1 month ~ 2.5 million seconds
1 million requests/day ~ 12 requests/second
QPS       = daily requests / 86,400
Peak QPS  ~ 2x to 10x average
Storage   = items x size x retention
Bandwidth = QPS x response size
1 KB = 10^3 bytes, 1 MB = 10^6, 1 GB = 10^9, 1 TB = 10^12
A single modern server: roughly 1,000s of simple requests/second
A single Postgres/MySQL primary: roughly 1,000s of writes/second
Redis: roughly 100,000 operations/second per node
```

## Load Balancing

```
nginx -T | grep -A8 upstream
curl -s http://<lb>/whoami
curl -sI http://<lb>/ | grep -i set-cookie
haproxy -c -f /etc/haproxy/haproxy.cfg
echo "show stat" | socat stdio /run/haproxy/admin.sock
```

Concepts: L4 vs L7, round robin / least connections / consistent hash,
health checks, connection draining, sticky sessions vs stateless servers.

## Caching (Redis)

```
redis-cli SET <key> <value> EX <seconds>
redis-cli GET <key>
redis-cli TTL <key>
redis-cli DEL <key>
redis-cli INFO stats | grep keyspace
redis-cli CONFIG GET maxmemory-policy
redis-cli --bigkeys
redis-cli INCR <key>
redis-cli EXPIRE <key> <seconds>
```

Concepts: cache-aside, write-through, write-behind, TTLs with jitter,
invalidation, eviction policies (LRU/LFU), stampedes, hot keys.

## Databases

```
psql -c "EXPLAIN ANALYZE <query>"
psql -c "CREATE INDEX CONCURRENTLY <name> ON <table> (<columns>)"
psql -c "\d <table>"
psql -c "SELECT client_addr, state, replay_lag FROM pg_stat_replication;"
psql -c "SELECT pg_is_in_recovery();"
psql -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
psql -c "SHOW max_connections;"
```

Concepts: indexes and query plans, SQL vs NoSQL, replication (sync vs
async), read replicas and replication lag, connection pooling, sharding
(hash vs range), consistent hashing, hot partitions.

## Messaging (Kafka)

```
kafka-topics.sh --bootstrap-server <host:9092> --describe --topic <topic>
kafka-topics.sh --bootstrap-server <host:9092> --alter --topic <topic> --partitions <n>
kafka-consumer-groups.sh --bootstrap-server <host:9092> --describe --group <group>
kafka-console-consumer.sh --bootstrap-server <host:9092> --topic <topic> --from-beginning --max-messages 5
```

Concepts: queues vs logs, partitions and ordering, consumer groups and
lag, at-most/at-least/exactly-once, idempotency, dead-letter queues,
backpressure.

## Consistency and Coordination

```
etcdctl endpoint status --cluster -w table
etcdctl member list -w table
```

Concepts: CAP, strong vs eventual consistency, quorum (W + R > N), leader
election, split brain, idempotency keys.

## Edge, APIs, and Rate Limiting

```
curl -sI <url> | grep -Ei 'cache-control|age|x-cache|etag'
curl -i <url>
curl -i -X POST <url> -H 'Idempotency-Key: <uuid>' -d '<body>'
dig +short <name>
```

Concepts: CDN caching and cache busting, rate limiting (fixed window,
sliding window, token bucket), pagination, idempotent APIs, 301 vs 302.

## A Design Review Checklist

1. Requirements: functional, and non-functional (scale, latency, availability).
2. Estimates: QPS, storage, bandwidth.
3. API and data model.
4. High-level architecture.
5. Bottlenecks and how each scales.
6. Failure modes: what happens when each component dies.
7. Trade-offs made, and what you'd do with more time.

## Going Deeper

```
psql -c "SELECT count(*) FROM outbox WHERE published_at IS NULL;"          # the outbox pattern's backlog
psql -c "BEGIN; INSERT INTO orders ...; INSERT INTO outbox ...; COMMIT;"   # one transaction, two rows
etcdctl endpoint status --cluster -w table        # leader, raft term, raft index
etcdctl endpoint health --cluster
etcdctl member list -w table
redis-cli PFADD visitors:2026-10-02 <id>          redis-cli PFCOUNT visitors:2026-10-02     # HyperLogLog
redis-cli BF.ADD seen_urls <url>                  redis-cli BF.EXISTS seen_urls <url>       # Bloom filter
redis-cli MEMORY USAGE <key>
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" \
     -H "Sec-WebSocket-Key: <key>" https://<host>/ws
wscat -c wss://<host>/ws
curl -N https://<host>/events                     # server-sent events stream
```

Concepts: the dual-write problem, transactional outbox, sagas and
compensation, two-phase commit, CQRS and event sourcing, active-passive
vs active-active regions, conflict resolution, quorum (n/2 + 1), Bloom
filters and HyperLogLog, WebSockets vs server-sent events vs long
polling, fan-out on write vs fan-out on read.
