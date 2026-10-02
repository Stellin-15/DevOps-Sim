# Kubernetes Command Reference — Full List

Everything from our conversation, consolidated, plus additions. Organized by category so it's easy to pull from when writing scenario JSON. Use this as the master source when generating `expected_commands` and `fake_output` for new scenarios.

---

## 1. Cluster & Context

```
kubectl cluster-info
kubectl cluster-info dump
kubectl version
kubectl get nodes
kubectl get nodes -o wide
kubectl describe node <name>
kubectl config get-contexts
kubectl config current-context
kubectl config use-context <name>
kubectl config view
kubectl config set-cluster <name> --server=<url>
kubectl config set-credentials <user> --token=<token>
kubectl config set-context --current --namespace=<ns>
kubectl config delete-context <name>
```

## 2. Namespaces

```
kubectl get ns
kubectl get namespaces
kubectl create ns <name>
kubectl create namespace <name>
kubectl delete ns <name>
kubectl describe ns <name>
kubectl get all -n <namespace>
kubectl get all -A
```

## 3. Pods

```
kubectl get pods
kubectl get pods -A
kubectl get pods -o wide
kubectl get pods -o yaml
kubectl get pods -o json
kubectl get pods --show-labels
kubectl get pods -l app=nginx
kubectl get pods -l 'env in (prod,staging)'
kubectl get pods --field-selector=status.phase=Running
kubectl get pods --sort-by=.metadata.creationTimestamp
kubectl get pod <name>
kubectl describe pod <name>
kubectl run <name> --image=<image>
kubectl run <name> --image=<image> --port=<port>
kubectl run <name> --image=<image> --env="KEY=value"
kubectl run <name> --image=<image> --restart=Never
kubectl run <name> --image=<image> --dry-run=client -o yaml
kubectl delete pod <name>
kubectl delete pod <name> --grace-period=0 --force
kubectl delete pods -l app=nginx
kubectl logs <pod>
kubectl logs <pod> -f
kubectl logs <pod> --previous
kubectl logs <pod> -c <container>
kubectl logs <pod> --since=1h
kubectl logs <pod> --tail=50
kubectl exec -it <pod> -- /bin/bash
kubectl exec -it <pod> -- /bin/sh
kubectl exec <pod> -- <command>
kubectl exec -it <pod> -c <container> -- /bin/bash
kubectl cp <pod>:/path/in/pod ./local-path
kubectl cp ./local-file <pod>:/path/in/pod
kubectl port-forward <pod> 8080:80
kubectl label pod <name> env=prod
kubectl label pod <name> env-
kubectl annotate pod <name> description="test pod"
kubectl top pod <name>
kubectl top pods
kubectl wait --for=condition=Ready pod/<name> --timeout=60s
kubectl debug <pod> -it --image=busybox --target=<container>
```

## 4. Deployments

```
kubectl get deployments
kubectl get deploy
kubectl get deploy -o wide
kubectl describe deployment <name>
kubectl create deployment <name> --image=<image>
kubectl create deployment <name> --image=<image> --replicas=3
kubectl create deployment <name> --image=<image> --dry-run=client -o yaml
kubectl scale deployment <name> --replicas=3
kubectl autoscale deployment <name> --min=2 --max=10 --cpu-percent=80
kubectl rollout status deployment <name>
kubectl rollout history deployment <name>
kubectl rollout history deployment <name> --revision=2
kubectl rollout undo deployment <name>
kubectl rollout undo deployment <name> --to-revision=2
kubectl rollout restart deployment <name>
kubectl rollout pause deployment <name>
kubectl rollout resume deployment <name>
kubectl set image deployment/<name> <container>=<image>
kubectl edit deployment <name>
kubectl delete deployment <name>
kubectl patch deployment <name> -p '{"spec":{"replicas":5}}'
kubectl expose deployment <name> --port=80 --target-port=8080 --type=ClusterIP
```

## 5. ReplicaSets

```
kubectl get replicasets
kubectl get rs
kubectl describe rs <name>
kubectl delete rs <name>
kubectl delete rs <name> --cascade=orphan
```

## 6. StatefulSets

```
kubectl get statefulsets
kubectl get sts
kubectl describe sts <name>
kubectl scale statefulset <name> --replicas=3
kubectl delete sts <name>
kubectl delete sts <name> --cascade=orphan
kubectl rollout status statefulset <name>
```

## 7. DaemonSets

```
kubectl get daemonsets
kubectl get ds
kubectl describe ds <name>
kubectl delete ds <name>
kubectl rollout status daemonset <name>
```

## 8. Jobs & CronJobs

```
kubectl get jobs
kubectl describe job <name>
kubectl create job <name> --image=<image>
kubectl create job <name> --image=<image> -- <command>
kubectl delete job <name>
kubectl get cronjobs
kubectl get cj
kubectl describe cronjob <name>
kubectl create cronjob <name> --image=<image> --schedule="*/5 * * * *"
kubectl create job --from=cronjob/<name> <manual-run-name>
kubectl delete cronjob <name>
```

## 9. Services & Networking

```
kubectl get svc
kubectl get services
kubectl get svc -o wide
kubectl describe svc <name>
kubectl expose deployment <name> --port=80 --target-port=8080
kubectl expose deployment <name> --port=80 --type=NodePort
kubectl expose deployment <name> --port=80 --type=LoadBalancer
kubectl expose pod <name> --port=80
kubectl delete svc <name>
kubectl get endpoints
kubectl get ep
kubectl get ingress
kubectl get ing
kubectl describe ingress <name>
kubectl delete ingress <name>
kubectl get networkpolicies
kubectl get netpol
kubectl describe networkpolicy <name>
kubectl proxy
```

## 10. ConfigMaps & Secrets

```
kubectl get configmaps
kubectl get cm
kubectl describe configmap <name>
kubectl create configmap <name> --from-literal=key=value
kubectl create configmap <name> --from-file=path/
kubectl create configmap <name> --from-file=key=path/to/file
kubectl create configmap <name> --from-env-file=path/to/.env
kubectl get configmap <name> -o yaml
kubectl delete configmap <name>
kubectl get secrets
kubectl describe secret <name>
kubectl create secret generic <name> --from-literal=key=value
kubectl create secret generic <name> --from-file=path/to/file
kubectl create secret docker-registry <name> --docker-server=<server> --docker-username=<user> --docker-password=<pass>
kubectl create secret tls <name> --cert=path/to/cert --key=path/to/key
kubectl get secret <name> -o yaml
kubectl get secret <name> -o jsonpath='{.data.password}' | base64 --decode
kubectl delete secret <name>
```

## 11. Storage (Volumes)

```
kubectl get pv
kubectl get persistentvolumes
kubectl describe pv <name>
kubectl delete pv <name>
kubectl get pvc
kubectl get persistentvolumeclaims
kubectl describe pvc <name>
kubectl delete pvc <name>
kubectl get storageclass
kubectl get sc
kubectl describe storageclass <name>
```

## 12. RBAC & Service Accounts

```
kubectl get serviceaccounts
kubectl get sa
kubectl create serviceaccount <name>
kubectl describe sa <name>
kubectl delete sa <name>
kubectl get roles
kubectl describe role <name>
kubectl get rolebindings
kubectl describe rolebinding <name>
kubectl get clusterroles
kubectl describe clusterrole <name>
kubectl get clusterrolebindings
kubectl create role <name> --verb=get,list,watch --resource=pods
kubectl create rolebinding <name> --role=<role> --serviceaccount=<ns>:<sa>
kubectl create clusterrolebinding <name> --clusterrole=<role> --serviceaccount=<ns>:<sa>
kubectl auth can-i create pods
kubectl auth can-i create pods --as=<user>
kubectl auth can-i --list
```

## 13. Resource Limits, Quotas, Autoscaling

```
kubectl get resourcequotas
kubectl get quota
kubectl describe resourcequota <name>
kubectl get limitranges
kubectl describe limitrange <name>
kubectl get hpa
kubectl describe hpa <name>
kubectl delete hpa <name>
kubectl top nodes
kubectl top pods
kubectl top pods --containers
kubectl top pods -A --sort-by=cpu
kubectl top pods -A --sort-by=memory
```

## 14. Labels, Selectors, Annotations

```
kubectl get pods --show-labels
kubectl label pod <name> key=value
kubectl label pod <name> key=value --overwrite
kubectl label pod <name> key-
kubectl get pods -l key=value
kubectl get pods -l 'key in (value1,value2)'
kubectl get pods -l 'key notin (value1)'
kubectl annotate pod <name> key=value
kubectl annotate pod <name> key-
```

## 15. Scheduling (Taints, Tolerations, Affinity)

```
kubectl taint nodes <node> key=value:NoSchedule
kubectl taint nodes <node> key=value:NoExecute
kubectl taint nodes <node> key:NoSchedule-
kubectl describe node <name>
kubectl cordon <node>
kubectl uncordon <node>
kubectl drain <node> --ignore-daemonsets
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
kubectl drain <node> --force
```

## 16. Events, Debugging, Diagnostics

```
kubectl get events
kubectl get events -A
kubectl get events --sort-by=.metadata.creationTimestamp
kubectl get events --field-selector involvedObject.name=<pod-name>
kubectl describe pod <name>
kubectl logs <pod>
kubectl logs <pod> --previous
kubectl exec -it <pod> -- /bin/sh
kubectl debug <pod> -it --image=busybox --target=<container>
kubectl debug node/<node> -it --image=busybox
kubectl get pod <name> -o jsonpath='{.status.phase}'
kubectl get pod <name> -o jsonpath='{.status.containerStatuses[0].restartCount}'
kubectl api-resources
kubectl api-versions
kubectl explain pod
kubectl explain pod.spec
kubectl explain pod.spec.containers
kubectl explain deployment.spec.strategy
```

## 17. Applying, Editing, Diffing Manifests

```
kubectl apply -f file.yaml
kubectl apply -f ./manifests/
kubectl apply -k ./
kubectl create -f file.yaml
kubectl delete -f file.yaml
kubectl diff -f file.yaml
kubectl edit pod <name>
kubectl edit deployment <name>
kubectl replace -f file.yaml
kubectl replace --force -f file.yaml
kubectl get deployment <name> -o yaml > backup.yaml
kubectl kustomize ./
```

## 18. CRDs & Custom Resources

```
kubectl get crd
kubectl get customresourcedefinitions
kubectl describe crd <name>
kubectl api-resources --api-group=<group>
kubectl get <custom-resource-kind>
kubectl describe <custom-resource-kind> <name>
```

## 19. Helm (package manager, not kubectl — but essential alongside it)

```
helm install <release> <chart>
helm install <release> <chart> --values values.yaml
helm install <release> <chart> --set key=value
helm list
helm status <release>
helm upgrade <release> <chart>
helm upgrade --install <release> <chart>
helm rollback <release> <revision>
helm uninstall <release>
helm show values <chart>
helm template <chart>
helm repo add <name> <url>
helm repo update
helm search repo <keyword>
```

## 20. Kubeconfig / Multi-cluster

```
export KUBECONFIG=~/.kube/config
export KUBECONFIG=~/.kube/config:~/.kube/other-config
kubectl config get-contexts
kubectl config use-context <name>
kubectl config rename-context <old> <new>
kubectl config delete-cluster <name>
```

## 21. Tooling & Shortcuts

```
alias k=kubectl
kubectl completion bash
kubectl completion zsh
kubectl explain <resource>
kubectl get all
```

Common short resource names to know:
```
po      = pods
deploy  = deployments
svc     = services
ns      = namespaces
cm      = configmaps
rs      = replicasets
sts     = statefulsets
ds      = daemonsets
cj      = cronjobs
pv      = persistentvolumes
pvc     = persistentvolumeclaims
sc      = storageclass
sa      = serviceaccounts
ep      = endpoints
ing     = ingress
netpol  = networkpolicies
hpa     = horizontalpodautoscaler
crd     = customresourcedefinition
```

## Ecosystem: Kustomize, Helm Authoring, Gateway API, Autoscalers, GitOps, Mesh

```
kubectl kustomize overlays/prod              # render, don't apply
kubectl diff -k overlays/prod
kubectl apply -k overlays/prod
kustomize edit set image shop=registry.example.com/shop:1.8.2

helm create <chart>
helm lint <chart>
helm template <release> <chart> -f values-prod.yaml
helm upgrade --install <release> <chart> -n <ns> --atomic --timeout 5m
helm history <release> -n <ns>         helm rollback <release> <revision> -n <ns>
helm get values <release> -n <ns>      helm get manifest <release> -n <ns>
helm package <chart>

kubectl get gatewayclass
kubectl get gateway -A
kubectl get httproute -A               kubectl describe httproute <name> -n <ns>
kubectl get referencegrant -A

kubectl describe vpa <name> -n <ns>
kubectl get scaledobject -n <ns>       kubectl describe scaledobject <name> -n <ns>
kubectl get nodepool                   kubectl describe nodepool <name>
kubectl get nodeclaim
kubectl logs -n kube-system deployment/karpenter

flux get kustomizations -A             flux get sources git -A
flux reconcile kustomization <name> --with-source
flux suspend kustomization <name>      flux resume kustomization <name>
flux logs --level=error

linkerd check
linkerd viz stat deploy -n <ns>
linkerd viz edges deployment -n <ns>
linkerd viz tap deploy/<name> -n <ns>
```

## Backup, Multi-Cluster, and Multi-Tenancy

```
velero backup create <name> --include-namespaces <ns>
velero backup describe <name> --details
velero backup get                      velero schedule get
velero restore create --from-backup <name>
velero restore describe <name>
kubectl get volumesnapshot -n <ns>     kubectl get volumesnapshotclass

kubectl get clusters -A                kubectl get machines -A          # Cluster API
clusterctl describe cluster <name>
kubectl get applicationsets -n argocd
argocd cluster list

kubectl describe resourcequota -n <ns>
kubectl describe limitrange -n <ns>
kubectl get networkpolicy -n <ns>
kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa> -n <ns>
vcluster list                          vcluster connect <name> -n <ns>
```

---

*This file is a reference for writing scenario JSON — pull `expected_commands` values from here so the game teaches syntax that actually matches real kubectl.*
