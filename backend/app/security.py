"""Teacher access, upload checks and security headers (docs/security.md).

Teachers sign in with a PIN (TEACHER_PIN) and get a signed, expiring token
(HMAC-SHA256 with AKSHAR_SECRET). Every teacher / child-mode endpoint needs
it; only /api/health, /api/auth/login and the parent page (random token in
the link) are public.
"""

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

TOKEN_TTL_S = 12 * 3600
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_S = 10 * 60
MIN_PIN_LEN = 6
MIN_SECRET_LEN = 32


class AuthConfig:
    def __init__(self, pin: str, secret: str):
        if len(pin) < MIN_PIN_LEN:
            raise RuntimeError(f"TEACHER_PIN must be at least {MIN_PIN_LEN} characters")
        if len(secret) < MIN_SECRET_LEN:
            raise RuntimeError(f"AKSHAR_SECRET must be at least {MIN_SECRET_LEN} characters")
        self.pin = pin
        self.key = secret.encode("utf-8")
        self._failures: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    # --- tokens --------------------------------------------------------------------

    def _sign(self, body: bytes) -> str:
        return base64.urlsafe_b64encode(hmac.new(self.key, body, hashlib.sha256).digest()).decode().rstrip("=")

    def issue_token(self, now: float | None = None) -> tuple[str, int]:
        exp = int((now or time.time()) + TOKEN_TTL_S)
        body = base64.urlsafe_b64encode(json.dumps({"exp": exp, "n": secrets.token_hex(8)}).encode()).decode().rstrip("=")
        return f"{body}.{self._sign(body.encode())}", exp

    def token_valid(self, token: str, now: float | None = None) -> bool:
        try:
            body, sig = token.split(".", 1)
            if not hmac.compare_digest(sig, self._sign(body.encode())):
                return False
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            return int(payload["exp"]) > (now or time.time())
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False

    # --- login with brute-force protection -------------------------------------------

    def check_pin(self, pin: str, client: str, now: float | None = None) -> bool:
        now = now or time.time()
        with self._lock:
            q = self._failures[client]
            while q and now - q[0] > LOGIN_WINDOW_S:
                q.popleft()
            if len(q) >= LOGIN_MAX_FAILURES:
                raise HTTPException(429, "Too many wrong PINs. Try again in 10 minutes.")
            ok = hmac.compare_digest(pin.encode("utf-8"), self.pin.encode("utf-8"))
            if ok:
                q.clear()
            else:
                q.append(now)
            return ok


def client_id(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def require_teacher(request: Request) -> None:
    auth: AuthConfig = request.app.state.auth
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token or not auth.token_valid(token):
        raise HTTPException(401, "Sign in as a teacher first", headers={"WWW-Authenticate": "Bearer"})


# --- uploads -----------------------------------------------------------------------------

def sniff_audio(data: bytes) -> str | None:
    """File extension from the bytes themselves, or None if it isn't a supported audio format."""
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return ".webm"
    if data[:4] == b"OggS":
        return ".ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ".wav"
    if data[:4] == b"fLaC":
        return ".flac"
    if data[4:8] == b"ftyp":
        return ".m4a"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return ".mp3"
    return None


# --- headers -------------------------------------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",  # reports and clips are children's data
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
