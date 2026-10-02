# Networking Command Reference (DevOps-Relevant)

## Connectivity Testing

```
ping <host>
ping -c 4 <host>
curl <url>
curl -I <url>
curl -v <url>
curl -o /dev/null -s -w "%{http_code}\n" <url>
curl --max-time 5 <url>
wget <url>
telnet <host> <port>
nc -zv <host> <port>
nc -zv <host> 20-30
traceroute <host>
mtr <host>
```

## DNS

```
nslookup <domain>
dig <domain>
dig <domain> +short
dig @<dns-server> <domain>
dig -x <ip>
dig <domain> MX
dig <domain> ANY
host <domain>
cat /etc/resolv.conf
cat /etc/hosts
```

## Ports & Sockets

```
ss -tulnp
netstat -tulnp
lsof -i :<port>
lsof -i tcp:<port>
nmap <host>
nmap -p 1-1000 <host>
nmap -sV <host>
```

## Interfaces & Routing

```
ip addr
ip addr show
ip route
ip route get <ip>
ifconfig
route -n
arp -a
```

## Firewall

```
iptables -L
iptables -L -n -v
ufw status
ufw allow <port>
ufw deny <port>
firewall-cmd --list-all
firewall-cmd --add-port=<port>/tcp --permanent
firewall-cmd --reload
```

## TLS / Certificates

```
openssl s_client -connect <host>:443
openssl x509 -in cert.pem -text -noout
openssl req -new -newkey rsa:2048 -nodes -keyout key.pem -out csr.pem
curl -vI https://<host> 2>&1 | grep -i "expire\|subject"
```

## HTTP Debugging

```
curl -X GET <url>
curl -X POST <url> -H "Content-Type: application/json" -d '{"key":"value"}'
curl -H "Authorization: Bearer <token>" <url>
curl -L <url>
curl -k <url>
curl --resolve <domain>:443:<ip> <url>
```

## Kubernetes-specific networking (bridges to the k8s category)

```
kubectl get svc
kubectl get endpoints
kubectl get networkpolicies
kubectl exec -it <pod> -- nslookup <service>
kubectl exec -it <pod> -- curl <service>:<port>
kubectl port-forward svc/<name> 8080:80
```

## Core concepts worth understanding (not just commands)

- OSI layers you'll actually debug at: L3 (IP/routing), L4 (TCP/UDP/ports), L7 (HTTP/DNS/TLS)
- DNS resolution order: /etc/hosts → local resolver → configured DNS server → (in k8s) CoreDNS
- A "connection refused" means the port is reachable but nothing is listening; a timeout usually means a firewall/security group/network policy is silently dropping packets — this distinction is the first branch point in almost every network debugging session
- NAT vs no-NAT matters for understanding why a pod's own IP looks different from outside vs inside the cluster

## Beyond the Basics: VPNs, BGP, DNS Delegation, HTTP/2 and gRPC, Cilium

```
sudo wg show                         sudo wg-quick up wg0        sudo wg-quick down wg0
sudo wg show wg0 latest-handshakes   ip route get <ip>

sudo vtysh -c "show bgp summary"
sudo vtysh -c "show ip bgp neighbors <peer> advertised-routes"
sudo vtysh -c "show ip route bgp"
sudo birdc show protocols

dig +trace <name>                    dig NS <zone> +short
dig SOA <zone> +short                dig @<nameserver> <name> +norecurse
dig +dnssec <name>                   named-checkzone <zone> <file>      rndc reload
kubectl -n kube-system get configmap coredns -o yaml

curl -sI --http2 https://<host>/     curl -sI --http3 https://<host>/
curl -s -o /dev/null -w "%{http_version}\n" https://<host>/
grpcurl <host>:443 list              grpcurl <host>:443 describe <service>
grpcurl -d '{"id": 1}' <host>:443 <service>/<method>
grpc_health_probe -addr=<host>:<port>

cilium status                        cilium connectivity test
hubble observe --namespace <ns> --verdict DROPPED
hubble observe --from-pod <ns>/<pod> --to-pod <ns>/<pod>
kubectl get ciliumnetworkpolicies -A

aws ec2 describe-vpc-peering-connections
aws ec2 describe-transit-gateway-attachments
aws ec2 search-transit-gateway-routes --transit-gateway-route-table-id <id> --filters Name=type,Values=static,propagated
aws ec2 describe-vpc-endpoints
```
