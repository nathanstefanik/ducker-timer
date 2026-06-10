# Deploy runbook

Target: Debian 12 LXC on the Proxmox box, public 80/443 forwarded to it,
Caddy terminating TLS, the timer bound to localhost.

## 1. Container

In the Proxmox UI: create an unprivileged Debian 12 LXC (1 core, 512 MB is
plenty). Note its LAN IP.

```sh
apt update
apt install -y python3 caddy git
```

## 2. App

```sh
git clone https://github.com/nathanstefanik/ducker-timer /opt/ducker-timer
cp /opt/ducker-timer/deploy/ducker-timer.service /etc/systemd/system/
systemctl enable --now ducker-timer
curl -s 127.0.0.1:8000/   # should print the create page
```

## 3. Caddy

```sh
cp /opt/ducker-timer/deploy/Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy
```

Caddy obtains and renews the Let's Encrypt certificate on its own once DNS
and port forwarding are in place.

## 4. DNS and port forwarding

- DNS: add an `A` record `timer.nathanstefanik.xyz -> <public IP>`.
- Router: forward TCP 80 and 443 to the LXC's LAN IP.

## 5. Update

```sh
cd /opt/ducker-timer && git pull && systemctl restart ducker-timer
```

Note: timer state is in-memory, so a restart drops live timers.
