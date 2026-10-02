# Server Fleet Operations Command Reference

Source material for `scenarios/servers/`: running tens to thousands of
servers, not one. Configuration management, patching, reboots, time,
storage, and backups.

## Ansible: Inventory & Ad-Hoc Commands

```
ansible-inventory -i inventory.ini --graph
ansible-inventory -i inventory.ini --list
ansible all -i inventory.ini -m ping
ansible web -i inventory.ini -m command -a "uptime"
ansible web -i inventory.ini -m shell -a "df -h / | tail -1"
ansible web -i inventory.ini -b -m apt -a "name=nginx state=latest"
ansible web -i inventory.ini -b -m service -a "name=nginx state=restarted"
ansible all -i inventory.ini -m setup -a "filter=ansible_distribution*"
ansible all -i inventory.ini --limit 'web[0]' -m ping
```

## Ansible: Playbooks

```
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-playbook -i inventory.ini site.yml --list-hosts
ansible-playbook -i inventory.ini site.yml --list-tasks
ansible-playbook -i inventory.ini site.yml --check --diff
ansible-playbook -i inventory.ini site.yml --limit <host-or-group>
ansible-playbook -i inventory.ini site.yml --tags <tag>
ansible-playbook -i inventory.ini site.yml --start-at-task "<name>"
ansible-playbook -i inventory.ini site.yml -e "var=value"
ansible-playbook -i inventory.ini site.yml --forks 20
ansible-lint site.yml
ansible-vault encrypt|decrypt|view|edit <file>
ansible-galaxy install -r requirements.yml
```

Key playbook keywords: `serial`, `max_fail_percentage`, `any_errors_fatal`,
`handlers`/`notify`, `become`, `when`, `register`, `delegate_to`,
`ansible.builtin.reboot`, `ansible.builtin.wait_for`.

## Patching (Debian/Ubuntu)

```
sudo apt update
apt list --upgradable
sudo apt upgrade -y
sudo unattended-upgrade --dry-run --debug
cat /etc/apt/apt.conf.d/50unattended-upgrades
cat /var/log/unattended-upgrades/unattended-upgrades.log
sudo apt-mark hold <pkg>
apt-mark showhold
sudo apt-mark unhold <pkg>
sudo needrestart -r l
ls /var/run/reboot-required
apt-cache policy <pkg>
sudo apt install <pkg>=<version>
```

## Patching (RHEL/Rocky/Fedora)

```
sudo dnf check-update
sudo dnf updateinfo list --security
sudo dnf upgrade --security -y
sudo dnf history
sudo dnf history info <id>
sudo dnf history undo <id>
sudo dnf versionlock add <pkg>
sudo dnf versionlock list
sudo needs-restarting -r
sudo needs-restarting -s
systemctl status dnf-automatic.timer
```

## Kernels & Reboots

```
uname -r
rpm -q kernel
dpkg -l 'linux-image-*' | grep ^ii
sudo apt autoremove --purge
sudo package-cleanup --oldkernels --count=2
sudo dnf remove --oldinstallonly --setopt installonly_limit=2 kernel
df -h /boot
sudo canonical-livepatch status
sudo kpatch list
sudo shutdown -r +5 "Rebooting for kernel update"
last reboot | head
```

## Cloud Fleet Patching (AWS SSM)

```
aws ssm describe-instance-patch-states --instance-ids <i-id>
aws ssm describe-instance-patches --instance-id <i-id> --filters Key=State,Values=Missing
aws ssm send-command --document-name AWS-RunPatchBaseline --targets Key=tag:PatchGroup,Values=<group> --parameters Operation=Scan
aws ssm send-command --document-name AWS-RunPatchBaseline --targets Key=tag:PatchGroup,Values=<group> --parameters Operation=Install --max-concurrency 10% --max-errors 1
aws ssm list-command-invocations --command-id <id> --details
```

## Time Synchronization

```
timedatectl
timedatectl set-timezone UTC
chronyc tracking
chronyc sources -v
sudo chronyc makestep
sudo systemctl restart chronyd
```

## Storage: LVM & Growing Filesystems

```
lsblk
sudo pvs; sudo vgs; sudo lvs
sudo growpart /dev/nvme0n1 1
sudo pvresize /dev/nvme0n1p3
sudo lvextend -r -l +100%FREE /dev/<vg>/<lv>
sudo resize2fs /dev/<vg>/<lv>
sudo xfs_growfs /
df -h
```

## Backups & Restores

```
restic -r <repo> init
restic -r <repo> backup /etc /var/lib/app
restic -r <repo> snapshots
restic -r <repo> check
restic -r <repo> restore latest --target /tmp/restore-test
restic -r <repo> forget --keep-daily 7 --keep-weekly 4 --prune
borg create <repo>::{hostname}-{now} /etc /srv
borg list <repo>
borg extract --dry-run <repo>::<archive>
pg_dump -Fc <db> > db.dump
pg_restore -d <scratch_db> db.dump
```

## Logs & Housekeeping

```
sudo logrotate -d /etc/logrotate.d/<app>
sudo logrotate -f /etc/logrotate.d/<app>
journalctl --disk-usage
sudo journalctl --vacuum-size=500M
systemctl list-timers
```

## Shared and Distributed Storage: NFS and Ceph

```
showmount -e <server>
sudo mount -t nfs <server>:/export/data /mnt/data
sudo mount -t nfs -o soft,timeo=50,retrans=3 <server>:/export/data /mnt/data
mount | grep nfs          nfsstat -m          cat /etc/exports
sudo exportfs -ra         sudo exportfs -v
sudo umount -f -l /mnt/data

ceph status               ceph health detail
ceph osd tree             ceph osd df
ceph df                   ceph pg stat
ceph osd out <id>         ceph osd in <id>
kubectl -n rook-ceph get cephcluster
kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph status
```
