import json
import random
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from words import new_code

STATIC = Path(__file__).parent / "static"
EXPIRY_S = 24 * 3600
MAX_DURATION_S = 99 * 3600 + 99 * 60 + 99

# in-memory by design: a restart drops live timers, an acceptable trade-off
# for a toy shared among friends for at most a day
timers = {}


def collect_garbage():
    now = time.time()
    dead = [
        code for code, t in timers.items()
        if (t["started_at"] or t["created_at"]) + t["duration_s"] + EXPIRY_S < now
    ]
    for code in dead:
        del timers[code]


def state(code):
    t = timers[code]
    return {
        "duration_s": t["duration_s"],
        "started_at": t["started_at"],
        "seed": t["seed"],
        "names": t["names"],
        "dist": t["dist"],
        "look_seed": t["look_seed"],
        "server_now": time.time(),
    }


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def reply_file(self, name, content_type):
        self.reply(200, (STATIC / name).read_bytes(), content_type)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self.reply_file("index.html", "text/html")
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
        elif path == "/static/style.css":
            self.reply_file("style.css", "text/css")
        elif path == "/static/timer.js":
            self.reply_file("timer.js", "text/javascript")
        else:
            self.reply(404, b"not found\n", "text/plain")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/api/new":
            self.create_timer(body)
        elif self.path.startswith("/api/t/") and self.path.endswith("/start"):
            self.act(self.path[len("/api/t/"):-len("/start")], "start")
        elif self.path.startswith("/api/t/") and self.path.endswith("/reset"):
            self.act(self.path[len("/api/t/"):-len("/reset")], "reset")
        else:
            self.reply(404, {"error": "not found"})

    def create_timer(self, body):
        try:
            fields = json.loads(body)
            h, m, s = (int(fields[k]) for k in ("h", "m", "s"))
        except (ValueError, KeyError, TypeError):
            return self.reply(400, {"error": "h, m, s must be integers"})
        duration_s = h * 3600 + m * 60 + s
        if not all(0 <= v <= 99 for v in (h, m, s)) or duration_s < 1:
            return self.reply(400, {"error": "each field 0-99, total at least 1 second"})
        names = [str(n).strip()[:20] for n in fields.get("names") or []]
        names = [n for n in names if n] or [f"duck {i + 1}" for i in range(6)]
        if not 2 <= len(names) <= 12:
            return self.reply(400, {"error": "2 to 12 racer names"})
        dist = fields.get("dist", "normal")
        if dist not in ("normal", "uniform"):
            return self.reply(400, {"error": "dist must be normal or uniform"})
        collect_garbage()
        code = new_code()
        while code in timers:
            code = new_code()
        # shuffle with system entropy: lane (and hence duck look) assignment is random
        random.SystemRandom().shuffle(names)
        timers[code] = {
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
        self.reply(200, state(code))


ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
