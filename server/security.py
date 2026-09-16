import hashlib
import hmac
import secrets
import time
from collections import OrderedDict, deque


class Gate:
    def __init__(self, secret):
        self.secret = secret.encode()
        self.windows = OrderedDict()

    def session(self, cookie):
        if cookie and len(cookie) < 150:
            parts = cookie.split('.')
            if len(parts) == 3:
                identity, expiry, signature = parts
                expected = hmac.new(self.secret, f'{identity}.{expiry}'.encode(), hashlib.sha256).hexdigest()
                if expiry.isdigit() and int(expiry) > time.time() and hmac.compare_digest(signature, expected): return cookie, False
        payload = secrets.token_hex(16) + '.' + str(int(time.time()) + 86400)
        return payload + '.' + hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest(), True

    def allow(self, key, limit, seconds):
        current = time.monotonic()
        window = self.windows.setdefault(key, deque())
        self.windows.move_to_end(key)
        while window and window[0] <= current - seconds: window.popleft()
        while len(self.windows) > 10000: self.windows.popitem(last=False)
        if len(window) >= limit: return False
        window.append(current)
        return True
