# Databases Command Reference (Operations)

Source material for `scenarios/databases/`. This is the operator's side
of databases: connecting, reading what the server is doing, access
control, maintenance, backup and recovery, replication, and the two
other stores most teams also run (MySQL and Redis). PostgreSQL is the
main example. Indexes and query plans as a *design* choice, read
replicas, sharding, and connection pooling are introduced in System
Design; schema migrations in a deploy pipeline are in CI/CD.

## psql Essentials

```
psql -h <host> -U <user> -d <database>
psql "postgresql://<user>@<host>:5432/<database>?sslmode=require"
\conninfo                 # who and where am I
\l                        # databases
\dn                       # schemas
\dt                       # tables
\d <table>                # columns, indexes, constraints
\di+ <table>*             # indexes with sizes
\du                       # roles
\x                        # expanded (one column per line) output
\timing                   # show how long each statement takes
\e                        # edit the query in $EDITOR
\i <file.sql>             # run a file
\copy <table> TO 'out.csv' CSV HEADER
\q
psql -c "<sql>"           # one statement, then exit
psql -f <file.sql> -v ON_ERROR_STOP=1 -1     # a file, in one transaction
psql -At -c "<sql>"       # unaligned, tuples only: for scripts
```

## SQL You Need on Call

```
SELECT <cols> FROM <t> WHERE <cond> ORDER BY <col> DESC LIMIT <n>;
SELECT status, count(*) FROM orders GROUP BY status HAVING count(*) > 100;
SELECT o.id, c.email FROM orders o JOIN customers c ON c.id = o.customer_id;
SELECT ... FROM a LEFT JOIN b ON ... WHERE b.id IS NULL;      -- rows with no match
SELECT *, row_number() OVER (PARTITION BY customer_id ORDER BY created_at DESC) FROM orders;
WITH recent AS (SELECT ...) SELECT ... FROM recent;
SELECT count(*) FILTER (WHERE status = 'failed') FROM orders;
SELECT date_trunc('hour', created_at), count(*) FROM orders GROUP BY 1 ORDER BY 1;
```

## Transactions and Locks

```
BEGIN;  ...  COMMIT;  /  ROLLBACK;
SAVEPOINT <name>;  ROLLBACK TO SAVEPOINT <name>;
SHOW transaction_isolation;
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT ... FOR UPDATE;                 -- lock the rows you're about to change
SELECT ... FOR UPDATE SKIP LOCKED;     -- job-queue pattern
SET lock_timeout = '3s';
SET statement_timeout = '30s';
```

Concepts: ACID, READ COMMITTED vs REPEATABLE READ vs SERIALIZABLE, lost
updates, deadlocks (the server kills one side), lock queues.

## Roles and Privileges

```
CREATE ROLE <name> LOGIN PASSWORD '<pw>';
CREATE ROLE <group> NOLOGIN;
GRANT <group> TO <name>;
GRANT CONNECT ON DATABASE <db> TO <role>;
GRANT USAGE ON SCHEMA public TO <role>;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO <role>;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO <role>;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER ROLE <name> CONNECTION LIMIT 20;
ALTER ROLE <name> SET statement_timeout = '30s';
\du      \dp <table>
SELECT * FROM pg_hba_file_rules;       # who may connect, from where, how
SELECT pg_reload_conf();
```

## What Is the Server Doing Right Now

```
SELECT pid, usename, state, wait_event_type, now() - query_start AS runtime, query
  FROM pg_stat_activity WHERE state <> 'idle' ORDER BY runtime DESC;
SELECT pid, pg_blocking_pids(pid) AS blocked_by, query FROM pg_stat_activity
  WHERE cardinality(pg_blocking_pids(pid)) > 0;
SELECT pg_cancel_backend(<pid>);       # cancel the query, keep the session
SELECT pg_terminate_backend(<pid>);    # end the session
SELECT * FROM pg_locks WHERE NOT granted;
ALTER SYSTEM SET idle_in_transaction_session_timeout = '5min';
```

## Finding Slow Queries

```
CREATE EXTENSION pg_stat_statements;
SELECT calls, mean_exec_time, total_exec_time, query FROM pg_stat_statements
  ORDER BY total_exec_time DESC LIMIT 5;
EXPLAIN (ANALYZE, BUFFERS) <query>;
ALTER SYSTEM SET log_min_duration_statement = '500ms';
SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_stat_user_tables
  ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;
SELECT indexrelname, idx_scan FROM pg_stat_user_indexes WHERE idx_scan = 0;
ANALYZE <table>;
SELECT name, setting, pending_restart FROM pg_settings WHERE name = '<setting>';
```

## Vacuum, Bloat, and Wraparound

```
SELECT relname, n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze
  FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;
VACUUM (VERBOSE, ANALYZE) <table>;
VACUUM FULL <table>;                   # rewrites the table under an exclusive lock
pg_repack -t <table> -d <db>           # rewrites it online
ALTER TABLE <t> SET (autovacuum_vacuum_scale_factor = 0.01);
SELECT datname, age(datfrozenxid) FROM pg_database ORDER BY 2 DESC;
SELECT * FROM pg_prepared_xacts;
ROLLBACK PREPARED '<gid>';
REINDEX INDEX CONCURRENTLY <index>;
```

## Backup and Restore (Logical)

```
pg_dump -Fc -d <db> -f <file.dump>           # custom format: compressed, selective
pg_dump -Fd -j 4 -d <db> -f <dir>            # directory format, parallel
pg_dump -t <table> -d <db>                   # one table
pg_dump --schema-only -d <db>
pg_dumpall --globals-only > globals.sql      # roles and tablespaces
pg_restore -l <file.dump>                    # list contents
pg_restore -d <db> -j 4 <file.dump>
pg_restore -d <db> -t <table> --data-only <file.dump>
createdb <name>      dropdb <name>
```

## Physical Backup and Point-in-Time Recovery

```
SHOW archive_mode;    SHOW archive_command;    SHOW wal_level;
SELECT pg_current_wal_lsn();
SELECT * FROM pg_stat_archiver;              # last archived WAL, failures
pg_basebackup -h <primary> -U replicator -D <dir> -X stream -P
pgbackrest --stanza=<name> info
pgbackrest --stanza=<name> --type=full backup
pgbackrest --stanza=<name> --type=incr backup
pgbackrest --stanza=<name> check
pgbackrest --stanza=<name> --type=time --target="<timestamp>" --target-action=promote restore
SELECT pg_is_in_recovery();
```

Concepts: RPO (how much data you may lose) and RTO (how long recovery
takes); a backup that has never been restored is a hope, not a backup.

## Replication and Failover

```
SELECT client_addr, state, sync_state, replay_lag FROM pg_stat_replication;
SELECT now() - pg_last_xact_replay_timestamp();        # on a replica
SELECT slot_name, active, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn))
  FROM pg_replication_slots;
SELECT pg_drop_replication_slot('<name>');
SELECT pg_promote();
patronictl -c /etc/patroni.yml list
patronictl -c /etc/patroni.yml switchover
patronictl -c /etc/patroni.yml failover
patronictl -c /etc/patroni.yml reinit <cluster> <member>
pg_rewind --target-pgdata=<dir> --source-server="<conninfo>"
```

## MySQL for PostgreSQL People

```
mysql -h <host> -u <user> -p <database>
SHOW DATABASES;   SHOW TABLES;   DESCRIBE <table>;   SHOW CREATE TABLE <table>\G
SHOW FULL PROCESSLIST;        KILL <id>;
SHOW ENGINE INNODB STATUS\G   # latest deadlock, lock waits
EXPLAIN <query>;
SHOW REPLICA STATUS\G         # Seconds_Behind_Source, Replica_IO/SQL_Running
SHOW VARIABLES LIKE '<name>';   SHOW GLOBAL STATUS LIKE '<name>';
mysqldump --single-transaction --routines <db> > <file.sql>
pt-query-digest /var/log/mysql/slow.log
```

## Redis Operations

```
redis-cli -h <host> ping
redis-cli info memory | replication | persistence | stats
redis-cli config get maxmemory-policy
redis-cli config set maxmemory-policy allkeys-lru     redis-cli config rewrite
redis-cli --bigkeys          redis-cli --memkeys
redis-cli memory usage <key>
redis-cli slowlog get 10
redis-cli --latency
redis-cli --scan --pattern 'session:*' | head         # never KEYS * in production
redis-cli ttl <key>          redis-cli expire <key> <seconds>
redis-cli bgsave             redis-cli lastsave
redis-cli client list
redis-cli -p 26379 sentinel get-master-addr-by-name <name>
redis-cli cluster info       redis-cli cluster nodes
```
