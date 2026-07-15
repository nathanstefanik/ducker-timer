import json
import random
import secrets
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from words import new_code

STATIC = Path(__file__).parent / "static"
EXPIRY_S = 24 * 3600
MAX_DURATION_S = 99 * 3600 + 99 * 60 + 99

# in-memory by design: a restart drops live timers, an acceptable trade-off
# for a toy shared among friends for at most a day
timers = {}
rate_limits = defaultdict(list)
sse_conds = {}


def collect_garbage():
    now = time.time()
    dead = [
        code for code, t in timers.items()
        if (t["started_at"] or t["created_at"]) + t["duration_s"] + EXPIRY_S < now
    ]
    for code in dead:
        del timers[code]
        sse_conds.pop(code, None)


def state(code):
    t = timers[code]
    return {
        "title": t["title"],
        "duration_s": t["duration_s"],
        "started_at": t["started_at"],
        "seed": t["seed"],
        "names": t["names"],
        "dist": t["dist"],
        "look_seed": t["look_seed"],
        "server_now": time.time(),
    }


def notify_sse(code):
    if code in sse_conds:
        cond, _ = sse_conds[code]
        with cond:
            sse_conds[code][1] += 1
            cond.notify_all()


def check_rate_limit(ip, max_reqs=10, window=60):
    now = time.time()
    hits = rate_limits[ip] = [t for t in rate_limits[ip] if now - t < window]
    if len(hits) >= max_reqs:
        return False
    hits.append(now)
    return True


CSP = ("default-src 'self'; style-src 'self'; script-src 'self'; "
       "img-src 'self' data:; connect-src 'self'")


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(data)

    def reply_file(self, name, content_type):
        self.reply(200, (STATIC / name).read_bytes(), content_type)

    def client_ip(self):
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self.reply_file("index.html", "text/html")
        elif path.startswith("/api/t/") and path.endswith("/stream"):
            self.stream_sse(path[len("/api/t/"):-len("/stream")])
        elif path.startswith("/api/t/"):
            code = path[len("/api/t/"):]
            if code in timers:
                self.reply(200, state(code))
            else:
                self.reply(404, {"error": "no such timer"})
        elif path.startswith("/t/"):
            if path[len("/t/"):] in timers:
                self.reply_file("timer.html", "text/html")
            else:
                self.reply(404, b"no such timer\n", "text/plain")
        elif path.startswith("/static/"):
            name = path[len("/static/"):]
            if not name or "/" in name or name.startswith(".") or not (STATIC / name).is_file():
                self.reply(404, b"not found\n", "text/plain")
            else:
                ctype = {".css": "text/css", ".js": "text/javascript"}.get(
                    Path(name).suffix, "application/octet-stream")
                self.reply_file(name, ctype)
        else:
            self.reply(404, b"not found\n", "text/plain")

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if path == "/api/new":
            self.create_timer(body)
        elif path.startswith("/api/t/") and path.endswith("/start"):
            self.act(path[len("/api/t/"):-len("/start")], "start")
        elif path.startswith("/api/t/") and path.endswith("/reset"):
            self.act(path[len("/api/t/"):-len("/reset")], "reset")
        else:
            self.reply(404, {"error": "not found"})

    def create_timer(self, body):
        if not check_rate_limit(self.client_ip()):
            return self.reply(429, {"error": "too many timers, try again later"})
        try:
            fields = json.loads(body)
            h, m, s = (int(fields[k]) for k in ("h", "m", "s"))
        except (ValueError, KeyError, TypeError):
            return self.reply(400, {"error": "h, m, s must be integers"})
        duration_s = h * 3600 + m * 60 + s
        if not all(0 <= v <= 99 for v in (h, m, s)) or duration_s < 1:
            return self.reply(400, {"error": "each field 0-99, total at least 1 second"})
        title = str(fields.get("title") or "").strip()[:40]
        names = [str(n).strip()[:20] for n in fields.get("names") or []]
        names = [n for n in names if n] or [f"duck {i + 1}" for i in range(6)]
        if not 2 <= len(names) <= 12:
            return self.reply(400, {"error": "2 to 12 racer names"})
        dist = fields.get("dist", "normal")
        if dist not in ("normal", "uniform", "exponential"):
            return self.reply(400, {"error": "dist must be normal, uniform, or exponential"})
        collect_garbage()
        code = new_code()
        while code in timers:
            code = new_code()
        random.SystemRandom().shuffle(names)
        timers[code] = {
            "title": title,
            "duration_s": duration_s,
            "started_at": None,
            "seed": None,
            "names": names,
            "dist": dist,
            "look_seed": secrets.randbits(32),
            "created_at": time.time(),
        }
        self.reply(200, {"code": code})

    def act(self, code, action):
        if code not in timers:
            return self.reply(404, {"error": "no such timer"})
        t = timers[code]
        if action == "start" and t["started_at"] is None:
            t["started_at"] = time.time()
            t["seed"] = secrets.randbits(32)
        elif action == "reset":
            t["started_at"] = None
            t["seed"] = None
        notify_sse(code)
        self.reply(200, state(code))

    def stream_sse(self, code):
        if code not in timers:
            return self.reply(404, {"error": "no such timer"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        if code not in sse_conds:
            sse_conds[code] = [threading.Condition(), 0]
        cond = sse_conds[code][0]
        while code in timers:
            try:
                self.wfile.write(f"data: {json.dumps(state(code))}\n\n".encode())
                self.wfile.flush()
            except OSError:
                return
            with cond:
                cond.wait(timeout=1)


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
