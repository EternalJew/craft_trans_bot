"""Per-IP throttling, kept in memory.

The public booking and parcel forms have no login, and every booking pings the
owner's Telegram — so an unthrottled form is a spam cannon aimed at him. The
login form is the one gate in front of the passenger list. One process, one
uvicorn worker: a dict is enough; restart clears it, which is fine.
"""
import ipaddress
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status


def client_ip(request: Request) -> str:
    """The address of whoever is really calling.

    nginx (and ngrok in front of it) append to X-Forwarded-For; both sit on
    private Docker addresses. A caller can put anything in that header, but
    only to the left of the entry the real proxy appended — so the rightmost
    public address is the client. No public address at all means a direct hit
    from the LAN / a proxy, and the socket peer is the best we have.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    for raw in reversed(forwarded.split(",")):
        candidate = raw.strip()
        try:
            if ipaddress.ip_address(candidate).is_global:
                return candidate
        except ValueError:
            continue
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


class SlidingWindow:
    """At most `limit` hits per `window` seconds for each key."""

    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def _sweep(self, now: float) -> None:
        # forget keys that have gone quiet, so the dict does not grow forever
        if now - self._last_sweep < self.window:
            return
        self._last_sweep = now
        for key in [k for k, q in self._hits.items() if not q or now - q[-1] > self.window]:
            del self._hits[key]

    def hit(self, key: str) -> float:
        """Record a hit. Returns 0 if allowed, else seconds until the next slot."""
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return self.window - (now - q[0])
            q.append(now)
            return 0


class LoginGuard:
    """Failed logins per IP: a few are free, then each further one doubles
    the wait. Success clears the slate."""

    def __init__(self, free_attempts: int = 5, base_delay: float = 60, max_delay: float = 900):
        self.free_attempts = free_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._failures: dict[str, tuple[int, float]] = {}   # ip -> (count, locked_until)
        self._lock = threading.Lock()

    def check(self, key: str) -> float:
        """Seconds the caller still has to wait, 0 if they may try now."""
        with self._lock:
            count, until = self._failures.get(key, (0, 0))
            return max(0.0, until - time.monotonic())

    def failed(self, key: str) -> None:
        with self._lock:
            count, _ = self._failures.get(key, (0, 0))
            count += 1
            wait = 0.0
            if count >= self.free_attempts:
                wait = min(self.base_delay * 2 ** (count - self.free_attempts), self.max_delay)
            self._failures[key] = (count, time.monotonic() + wait)

    def succeeded(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def too_many(retry_after: float) -> HTTPException:
    seconds = max(1, int(retry_after + 0.999))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Забагато запитів. Спробуйте через {seconds} с.",
        headers={"Retry-After": str(seconds)},
    )


# Public forms: 5 submissions per 10 minutes from one address. A family
# booking a few seats fits; a script does not.
public_form = SlidingWindow(limit=5, window=600)
login_guard = LoginGuard()
