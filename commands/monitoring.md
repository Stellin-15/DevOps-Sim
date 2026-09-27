# Monitoring & Logging Command Reference

## Prometheus

```
promtool check config prometheus.yml
promtool check rules alerts.yml
curl http://localhost:9090/api/v1/query?query=up
curl http://localhost:9090/-/reload
```

PromQL query examples (what you'll actually type in the UI):
```
up
rate(http_requests_total[5m])
sum(rate(http_requests_total[5m])) by (service)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
increase(http_requests_total{status="500"}[1h])
avg_over_time(cpu_usage[10m])
```

## Grafana

```
curl -H "Authorization: Bearer <api-key>" http://localhost:3000/api/dashboards/db
curl -X POST http://localhost:3000/api/dashboards/db -H "Content-Type: application/json" -d @dashboard.json
```

## Logging — journald / syslog

```
journalctl -u <service>
journalctl -f
journalctl --since "1 hour ago"
journalctl --since today
journalctl -p err
journalctl -k
journalctl --disk-usage
journalctl --vacuum-time=7d
tail -f /var/log/syslog
tail -f /var/log/messages
```

## ELK / EFK Stack (Elasticsearch, Logstash/Fluentd, Kibana)

```
curl -X GET "localhost:9200/_cluster/health?pretty"
curl -X GET "localhost:9200/_cat/indices?v"
curl -X GET "localhost:9200/my-index/_search?q=error"
curl -X DELETE "localhost:9200/my-index"
curl -X GET "localhost:9200/_cat/nodes?v"
```

Kibana Query Language (KQL) examples:
```
status:500
service:"payments-api" and level:"error"
timestamp >= "2026-09-27" and message:"timeout"
```

## Loki (log aggregation, Grafana ecosystem)

```
logcli query '{app="checkout-service"}'
logcli query '{app="checkout-service"} |= "error"'
logcli query '{app="checkout-service"} | json | status_code="500"'
```

## Kubernetes-native monitoring commands

```
kubectl top nodes
kubectl top pods
kubectl top pods --containers
kubectl get --raw /metrics
kubectl logs -l app=myapp --all-containers
```

## Alerting concepts (Alertmanager)

```yaml
groups:
  - name: example
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status="500"}[5m]) > 0.05
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Error rate above 5% for 10 minutes"
```

## The "four golden signals" (SRE concept worth knowing cold)

- **Latency** — how long requests take
- **Traffic** — how much demand is on the system
- **Errors** — rate of failed requests
- **Saturation** — how "full" the system is (CPU, memory, disk, queue depth)

## Common debugging sequence when something is "slow" or "erroring"

```
kubectl top pods
kubectl logs -l app=myapp --tail=100
kubectl get events --sort-by=.metadata.creationTimestamp
curl -o /dev/null -s -w "%{time_total}\n" <url>
journalctl -u <service> --since "10 minutes ago"
```
