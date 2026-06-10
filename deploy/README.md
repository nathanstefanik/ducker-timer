# Deploy runbook

Target: the timer runs in its own Debian 12 LXC on the Proxmox box,
following the one-service-per-container pattern. The existing Caddy
instance on 192.168.1.220 terminates TLS and proxies to the timer LXC
over the LAN.

## 1. Container

In the Proxmox UI: create an unprivileged Debian 12 LXC (1 core, 512 MB is
plenty) with a static LAN IP. Note that IP.

```sh
apt update
apt install -y python3 git
```

## 2. App

```sh
git clone https://github.com/nathanstefanik/ducker-timer /opt/ducker-timer
cp /opt/ducker-timer/deploy/ducker-timer.service /etc/systemd/system/
systemctl enable --now ducker-timer
curl -s 127.0.0.1:8000/ | head -3   # should print the create page
```

The server binds 0.0.0.0:8000 so Caddy can reach it from another host.
It is only as exposed as the LAN; Caddy is the public face.

## 3. Caddy (on the existing Caddy host, 192.168.1.220)

Append the block from `Caddyfile` in this directory to `/etc/caddy/Caddyfile`,
substituting the timer LXC's IP, then:

```sh
systemctl reload caddy
```

Caddy obtains and renews the Let's Encrypt certificate on its own once DNS
is in place.

## 4. DNS

Add an `A` record `timer.nathanstefanik.xyz -> <public IP>` (same target as
vault/files/sync/joplin). Ports 80/443 already reach Caddy, so nothing new
to forward.

## 5. Update

```sh
cd /opt/ducker-timer && git pull && systemctl restart ducker-timer
```

Note: timer state is in-memory, so a restart drops live timers.
