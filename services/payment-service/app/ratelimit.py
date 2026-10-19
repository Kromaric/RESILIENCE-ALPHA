import time
from collections import deque


class SlidingWindowLimiter:
    """Limiteur en mémoire, par clé (IP), sur une fenêtre glissante.

    Local à chaque instance ; la limitation globale est assurée par le WAF.
    """

    def __init__(self, limit: int, window_seconds: float = 60.0, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > self.max_keys:
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - self.window}
