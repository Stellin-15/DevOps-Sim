# Linux Command Reference (DevOps-Relevant Subset)

## Navigation & Files

```
pwd
ls -la
cd <path>
mkdir -p <path>
rm -rf <path>
cp -r <src> <dest>
mv <src> <dest>
find / -name "<pattern>"
find / -type f -mtime -1
find / -size +100M
touch <file>
cat <file>
less <file>
head -n 50 <file>
tail -n 50 <file>
tail -f <file>
wc -l <file>
```

## Text Processing

```
grep "<pattern>" <file>
grep -r "<pattern>" <dir>
grep -i "<pattern>" <file>
grep -v "<pattern>" <file>
grep -n "<pattern>" <file>
sed 's/old/new/g' <file>
awk '{print $1}' <file>
sort <file>
sort -n <file>
uniq -c
cut -d',' -f1 <file>
diff <file1> <file2>
xargs
tr 'a-z' 'A-Z'
```

## Permissions & Ownership

```
chmod 755 <file>
chmod +x <file>
chmod -R 644 <dir>
chown user:group <file>
chown -R user:group <dir>
umask
sudo <command>
su - <user>
whoami
id
```

## Processes

```
ps aux
ps -ef
top
htop
kill <pid>
kill -9 <pid>
killall <process-name>
pkill <name>
pgrep <name>
nice -n 10 <command>
renice 10 -p <pid>
jobs
bg
fg
nohup <command> &
disown
```

## System Info & Resources

```
df -h
du -sh <dir>
du -sh *
free -h
uptime
uname -a
lscpu
lsblk
nproc
vmstat
iostat
sar
dmesg
dmesg -T | tail
journalctl
journalctl -u <service>
journalctl -f
journalctl --since "1 hour ago"
```

## Networking

```
ping <host>
curl <url>
curl -I <url>
curl -X POST <url> -d '{"key":"value"}'
wget <url>
netstat -tulnp
ss -tulnp
ss -tan
ifconfig
ip addr
ip route
nslookup <domain>
dig <domain>
traceroute <host>
telnet <host> <port>
nc -zv <host> <port>
hostname
hostname -I
```

## Services (systemd)

```
systemctl status <service>
systemctl start <service>
systemctl stop <service>
systemctl restart <service>
systemctl enable <service>
systemctl disable <service>
systemctl daemon-reload
systemctl list-units --type=service
journalctl -u <service> -f
```

## Archives & Compression

```
tar -czvf archive.tar.gz <dir>
tar -xzvf archive.tar.gz
tar -tzvf archive.tar.gz
zip -r archive.zip <dir>
unzip archive.zip
gzip <file>
gunzip <file>.gz
```

## Environment & Shell

```
echo $PATH
export VAR=value
env
printenv
which <command>
whereis <command>
alias ll='ls -la'
history
source ~/.bashrc
crontab -e
crontab -l
```

## SSH & Remote

```
ssh user@host
ssh -i key.pem user@host
scp file.txt user@host:/path
scp -r dir/ user@host:/path
rsync -avz src/ user@host:/dest/
ssh-keygen -t ed25519
ssh-copy-id user@host
```

## User & Group Management

```
useradd <name>
usermod -aG <group> <user>
userdel <name>
groupadd <name>
passwd <user>
cat /etc/passwd
cat /etc/group
```

## Disk & Filesystem

```
mount /dev/sdX /mnt
umount /mnt
fdisk -l
mkfs.ext4 /dev/sdX
fsck /dev/sdX
```
