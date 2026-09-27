# Security Command Reference (Defensive, DevOps-Relevant)

Source material for `scenarios/security/`. Everything here is for systems
you own or are authorized to test. Scanning other people's systems without
permission is illegal in most countries.

## Network Discovery & Port Scanning (nmap)

```
nmap -sn <cidr>                      # host discovery only
nmap <host>                          # top 1000 TCP ports
nmap -p- <host>                      # all 65535 TCP ports
nmap -sV -p <ports> <host>           # service/version detection
nmap -sU --top-ports 20 <host>       # UDP
nmap -Pn <host>                      # skip ping (hosts that drop ICMP)
nmap --script ssl-enum-ciphers -p 443 <host>
nmap --script vuln <host>
nmap -oA <basename> <host>           # save normal/XML/grepable output
ss -tulnp                            # what's listening, from the inside
```

## Vulnerability & Misconfiguration Scanning

```
trivy image <image>
trivy image --severity HIGH,CRITICAL --exit-code 1 <image>
trivy fs --scanners vuln,secret,misconfig .
trivy config <dir>
trivy k8s --report summary cluster
grype <image>
lynis audit system
lynis show details <test-id>
oscap xccdf eval --profile <profile> --results results.xml --report report.html <datastream>
kube-bench run --targets node
testssl.sh <host>:443
```

## Secrets Scanning

```
gitleaks detect --source . -v
gitleaks detect --source . --log-opts="--all"
trufflehog git file://. --only-verified
git log -p -S '<string>'
git filter-repo --replace-text <file>
```

## SSH & Access Hardening

```
sshd -T | grep -Ei 'permitrootlogin|passwordauthentication|pubkeyauthentication'
sudo sshd -t
sudo systemctl reload sshd
grep -E '^(PermitRootLogin|PasswordAuthentication)' /etc/ssh/sshd_config
awk -F: '$3 == 0' /etc/passwd
sudo -l -U <user>
getent group sudo
chage -l <user>
passwd -l <user>
```

## Brute-Force Protection

```
sudo fail2ban-client status
sudo fail2ban-client status sshd
sudo fail2ban-client set sshd unbanip <ip>
lastb | head
last -a | head
journalctl -u ssh --since "1 hour ago" | grep "Failed password"
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head
```

## Audit Logging & Endpoint Visibility

```
sudo auditctl -l
sudo auditctl -w /etc/passwd -p wa -k identity
sudo ausearch -k identity --start today
sudo aureport --auth --failed
osqueryi "SELECT pid, name, path, cmdline FROM processes WHERE on_disk = 0;"
osqueryi "SELECT * FROM listening_ports;"
osqueryi "SELECT * FROM crontab;"
osqueryi "SELECT username, uid FROM users WHERE uid = 0;"
sudo aide --init
sudo aide --check
```

## Investigating a Suspected Compromise

```
ps auxf
ps -eo pid,user,%cpu,cmd --sort=-%cpu | head
ls -l /proc/<pid>/exe
ls -la /tmp /var/tmp /dev/shm
ss -tnp state established
lsof -i -nP
crontab -l -u <user>
ls /etc/cron.* /var/spool/cron/crontabs
systemctl list-timers --all
systemctl list-unit-files --state=enabled
cat ~/.ssh/authorized_keys
find / -mtime -2 -type f -path '/var/www/*' 2>/dev/null
find /var/www -name '*.php' -newer <reference-file>
sha256sum <file>
```

## Containment

```
sudo iptables -I OUTPUT -d <ip> -j DROP
sudo nft add rule inet filter output ip daddr <ip> drop
sudo usermod -L <user>
sudo userdel -r <user>
crontab -r -u <user>
kill -STOP <pid>                     # freeze for forensics before killing
aws ec2 modify-instance-attribute --instance-id <i-id> --groups <quarantine-sg>
aws ec2 create-snapshot --volume-id <vol> --description "forensics"
```
