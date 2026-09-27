# SRE Command Reference (How Large Companies Run Production)

Source material for `scenarios/sre/`. Google's and Meta's internal tools
(Borg, Monarch, Tupperware, and so on) aren't public. This file uses the
open-source tools that descend from them or implement the same ideas:
Kubernetes (from Borg), Prometheus (inspired by Borgmon), and the
practices from the Google SRE books (SLOs, error budgets, blameless
postmortems, staged rollouts).

## Progressive Delivery (Argo Rollouts)

```
kubectl argo rollouts list rollouts -n <ns>
kubectl argo rollouts get rollout <name> -n <ns> --watch
kubectl argo rollouts set image <name> <container>=<image> -n <ns>
kubectl argo rollouts promote <name> -n <ns>
kubectl argo rollouts promote <name> -n <ns> --full
kubectl argo rollouts abort <name> -n <ns>
kubectl argo rollouts retry rollout <name> -n <ns>
kubectl argo rollouts undo <name> -n <ns>
kubectl get analysisrun -n <ns>
kubectl describe analysisrun <name> -n <ns>
```

## Service Mesh (Istio)

```
istioctl proxy-status
istioctl analyze -n <ns>
istioctl proxy-config cluster <pod> -n <ns>
istioctl proxy-config route <pod> -n <ns>
istioctl x describe pod <pod> -n <ns>
kubectl get virtualservice,destinationrule -n <ns>
kubectl apply -f <virtualservice-with-weights>.yaml
```

Resilience settings in DestinationRule/VirtualService: `retries`
(`attempts`, `perTryTimeout`, `retryOn`), `timeout`, `outlierDetection`
(circuit breaking/ejection), `connectionPool` (limits).

## Load Testing

```
k6 run script.js
k6 run --vus 100 --duration 5m script.js
k6 run -e BASE_URL=<url> script.js
echo "GET <url>" | vegeta attack -rate=500/s -duration=60s | vegeta report
echo "GET <url>" | vegeta attack -rate=500/s -duration=60s | tee results.bin | vegeta report -type=hist[0,50ms,100ms,250ms,500ms,1s]
hey -z 30s -c 50 <url>
```

## Capacity Planning (PromQL via promtool)

```
promtool query instant <prom-url> 'predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 4*3600) < 0'
promtool query instant <prom-url> 'max_over_time(sum(rate(http_requests_total[5m]))[30d:1h])'
promtool query instant <prom-url> 'sum(kube_pod_container_resource_requests{resource="cpu"}) / sum(kube_node_status_allocatable{resource="cpu"})'
promtool query range --start=<t> --end=<t> --step=1h <prom-url> '<expr>'
```

## Chaos Engineering

```
sudo tc qdisc add dev eth0 root netem delay 200ms 50ms
sudo tc qdisc add dev eth0 root netem loss 5%
sudo tc qdisc show dev eth0
sudo tc qdisc del dev eth0 root
stress-ng --cpu 4 --timeout 60s
stress-ng --vm 2 --vm-bytes 80% --timeout 60s
kubectl apply -f podchaos.yaml          # Chaos Mesh PodChaos / NetworkChaos
kubectl get podchaos,networkchaos -A
kubectl delete podchaos <name> -n <ns>
```

## Incident Response Tooling

```
kubectl rollout undo deployment/<name> -n <ns>
kubectl rollout history deployment/<name> -n <ns>
kubectl scale deployment <name> --replicas=<n> -n <ns>
kubectl set env deployment/<name> <FLAG>=false -n <ns>     # kill switch
redis-cli -h <host> INFO stats
redis-cli -h <host> --bigkeys
curl -s <service>/debug/vars
curl -s <service>/healthz
curl -s <service>/readyz
```

## Feature Flags & Config Rollouts

```
kubectl get configmap <name> -n <ns> -o yaml
kubectl apply -f <configmap>.yaml
kubectl rollout restart deployment/<name> -n <ns>
kubectl annotate deployment <name> -n <ns> kubernetes.io/change-cause="<why>"
curl -s -X PATCH <flag-service>/flags/<flag> -d '{"enabled":false}'
```

## Error Budgets & Reliability Reviews

```
promtool query instant <prom-url> '<SLI ratio over 28d>'
promtool check rules <slo-rules>.yml
promtool test rules <slo-tests>.yml
sloth generate -i <slo-spec>.yml
```
