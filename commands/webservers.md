# Web Servers and Proxies Command Reference

Source material for `scenarios/webservers/`. Almost every request to a
production system passes through a reverse proxy: nginx, HAProxy, Envoy,
or a cloud load balancer built on one of them. This file covers running
them: configuration, TLS, proxying, logs, limits, and reloads. nginx is
the main example, HAProxy the second. Load-balancing *algorithms* as a
design choice are in System Design; TLS and HTTP themselves (openssl,
curl) are in Networking.

## nginx: Running It

```
nginx -v            nginx -V                 # version; build options and modules
nginx -t                                     # test the configuration
nginx -T                                     # test, and print the whole effective config
nginx -s reload                              # or: systemctl reload nginx
systemctl status nginx
ps -o pid,ppid,cmd -C nginx                  # master and worker processes
ss -tlnp | grep nginx                        # what it's listening on
ls /etc/nginx/sites-enabled/   ls /etc/nginx/conf.d/
```

## nginx: Server Blocks and Locations

```
nginx -T | grep -E "server_name|listen"
curl -s -H "Host: <name>" http://127.0.0.1/          # test a virtual host directly
curl -sI http://<host>/<path>
```

```
server {
    listen 80 default_server;
    server_name shop.example.com;
    root /var/www/shop;
    location / { try_files $uri $uri/ =404; }
    location = /health { return 200 "ok\n"; }
    location /static/ { expires 7d; }
    location ~ \.php$ { ... }
}
```

Location matching order: exact (`=`), then the longest prefix (stopping
if it has `^~`), then regular expressions in file order, then the longest
prefix again.

## nginx: Reverse Proxy

```
upstream backend {
    least_conn;
    server 10.0.1.11:8080 max_fails=3 fail_timeout=10s;
    server 10.0.1.12:8080;
    keepalive 32;
}
location /api/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    proxy_next_upstream error timeout http_502;
}
```

Status codes: 502 the upstream answered badly or refused (or none are
live), 503 a limit rejected the request (HAProxy also uses it for 'no
healthy server'), 504 the upstream didn't answer in time, 499
the client gave up first, 413 body too large.

## nginx: TLS

```
listen 443 ssl;   http2 on;
ssl_certificate /etc/letsencrypt/live/<name>/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/<name>/privkey.pem;
ssl_protocols TLSv1.2 TLSv1.3;
add_header Strict-Transport-Security "max-age=31536000" always;
return 301 https://$host$request_uri;        # in the port-80 server
```

```
certbot --nginx -d <name>
certbot certonly --webroot -w /var/www/html -d <name>
certbot certificates
certbot renew --dry-run
systemctl list-timers | grep certbot
openssl s_client -connect <host>:443 -servername <name> </dev/null | openssl x509 -noout -dates -subject
```

## nginx: Logs

```
tail -f /var/log/nginx/access.log /var/log/nginx/error.log
awk '{print $9}' access.log | sort | uniq -c | sort -rn          # status codes
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head   # top client IPs
awk '$9 >= 500 {print $7}' access.log | sort | uniq -c | sort -rn | head
grep -c " 499 " access.log
log_format timed '$remote_addr "$request" $status $request_time $upstream_response_time $upstream_addr';
```

## nginx: Limits, Caching, and Hardening

```
limit_req_zone $binary_remote_addr zone=perip:10m rate=10r/s;
limit_req zone=perip burst=20 nodelay;
limit_conn_zone $binary_remote_addr zone=conns:10m;
client_max_body_size 20m;
proxy_cache_path /var/cache/nginx keys_zone=app:10m max_size=1g inactive=60m;
proxy_cache app;   proxy_cache_valid 200 5m;   add_header X-Cache-Status $upstream_cache_status;
gzip on;   gzip_types text/css application/json;
server_tokens off;
worker_processes auto;   worker_connections 4096;   worker_rlimit_nofile 65535;
curl -s http://127.0.0.1/nginx_status            # stub_status
```

## HAProxy

```
haproxy -c -f /etc/haproxy/haproxy.cfg           # check the configuration
systemctl reload haproxy
echo "show stat" | socat stdio /run/haproxy/admin.sock
echo "show servers state" | socat stdio /run/haproxy/admin.sock
echo "set server <backend>/<server> state drain" | socat stdio /run/haproxy/admin.sock
echo "set server <backend>/<server> state ready" | socat stdio /run/haproxy/admin.sock
echo "show info" | socat stdio /run/haproxy/admin.sock
```

```
frontend web
    bind :443 ssl crt /etc/haproxy/certs/site.pem
    default_backend app
backend app
    balance leastconn
    option httpchk GET /health
    server app1 10.0.1.11:8080 check
    server app2 10.0.1.12:8080 check
```

## Others Worth Recognising

```
envoy --mode validate -c envoy.yaml
curl -s localhost:9901/clusters                  # Envoy admin: upstream health
curl -s localhost:9901/config_dump
caddy validate --config Caddyfile     caddy reload
traefik: configured from labels/CRDs; dashboard and /api/http/routers
apachectl configtest      apachectl -S           # Apache: test, list virtual hosts
```
