# The Wider Landscape: Command Reference

Source material for `scenarios/landscape/`. These are the tools you meet
when a company made a different choice from the mainstream one, or made
its choice ten years ago. The aim is recognition: for each, how to see
what's running, how to check its health, and how it maps to what you
already know.

## Nomad and Consul

```
nomad node status                 nomad job status <job>
nomad job plan <file.nomad>       nomad job run <file.nomad>
nomad alloc status <id>           nomad alloc logs <id>
consul members                    consul catalog services
consul catalog nodes -service=<name>
dig @127.0.0.1 -p 8600 <service>.service.consul
docker service ls                 docker service ps <service>          # Swarm
```

## Puppet, Chef, and Salt

```
sudo puppet agent --test --noop   sudo puppet agent --test
puppet parser validate <file.pp>  puppet config print server
sudo chef-client --why-run        knife node list     knife node show <node>
sudo salt '*' test.ping           sudo salt '<target>' state.apply <state> test=True
sudo salt-key -L
```

## Other Container Tools

```
podman ps      podman run --rm -it <image>      podman generate systemd --new --name <ctr>
podman pod ls
buildah bud -t <image> .          skopeo inspect docker://<image>
skopeo copy docker://<src> docker://<dst>
sudo crictl ps                    sudo crictl pods            sudo crictl logs <id>
sudo crictl images                sudo crictl inspect <id>
sudo nerdctl -n k8s.io ps
kubectl get runtimeclass
```

## Kubernetes Distributions

```
oc get routes       oc get scc       oc adm policy add-scc-to-user <scc> -z <sa>
oc new-project <name>               oc get clusteroperators
sudo k3s kubectl get nodes          sudo systemctl status k3s
sudo k3s crictl ps
kubectl get ipaddresspools -n metallb-system
talosctl -n <node> health           talosctl -n <node> dmesg
```

## Build Systems

```
bazel build //...                 bazel test //...            bazel query 'deps(//app:server)'
bazel build //app:server --remote_cache=<url>
nix develop                       nix build                   nix flake update
nix-shell -p <package>
```

## Other Version Control

```
git push origin HEAD:refs/for/main            # Gerrit: push for review
git review                                    # git-review helper
p4 sync       p4 opened       p4 submit -d "<message>"
hg status     hg log -l 5     hg pull -u
```

## Windows Administration (PowerShell)

```
Get-Service -Name <name>          Restart-Service -Name <name>
Get-EventLog -LogName System -Newest 20 -EntryType Error
Get-WinEvent -LogName Application -MaxEvents 20
Get-Process | Sort-Object CPU -Descending | Select-Object -First 5
Test-NetConnection <host> -Port <port>
Enter-PSSession -ComputerName <host>
Invoke-Command -ComputerName <hosts> -ScriptBlock { <command> }
Get-ADUser -Identity <user> -Properties MemberOf
gpresult /r                       Get-WindowsFeature | Where-Object Installed
```

## Private Cloud, Virtualisation, and Bare Metal

```
openstack server list             openstack server show <name>
openstack network list            openstack hypervisor stats show
qm list       qm status <vmid>    pvecm status                # Proxmox
govc ls /dc/vm                    govc vm.info <name>         # vSphere
ipmitool -H <bmc> -U <user> -P <pass> chassis status
ipmitool -H <bmc> -U <user> -P <pass> sol activate
ipmitool -H <bmc> -U <user> -P <pass> chassis power cycle
curl -sk -u <user>:<pass> https://<bmc>/redfish/v1/Systems/1 | jq '.PowerState, .Status'
```

## Older Monitoring

```
/usr/lib/nagios/plugins/check_http -H <host> -u /health -w 1 -c 3
/usr/lib/nagios/plugins/check_disk -w 20% -c 10% -p /
sudo nagios -v /etc/nagios4/nagios.cfg
snmpwalk -v2c -c <community> <host> 1.3.6.1.2.1.2.2.1.2
snmpget -v2c -c <community> <host> sysUpTime.0
zabbix_get -s <host> -k system.cpu.load[all,avg1]
echo "shop.orders.placed:1|c" | nc -u -w0 127.0.0.1 8125      # StatsD counter
```

## High-Performance Computing (Slurm)

```
sinfo             squeue -u <user>          sbatch job.sh
srun --pty bash   scancel <jobid>           sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS
scontrol show job <jobid>                   scontrol show node <node>
```

## Mail and DNS Hygiene

```
dig TXT <domain> +short                       # SPF: v=spf1 ...
dig TXT <selector>._domainkey.<domain> +short # DKIM public key
dig TXT _dmarc.<domain> +short                # DMARC policy
dig MX <domain> +short
dig +dnssec <domain> SOA                      # RRSIG records present?
delv <domain>                                 # validates the DNSSEC chain
```

## Mobile Delivery

```
fastlane lanes                    fastlane ios beta           fastlane android deploy
fastlane match appstore --readonly
xcrun altool --list-apps          ./gradlew bundleRelease
```
