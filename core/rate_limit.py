import time
from collections.abc import Callable

from fastapi import HTTPException, Request


_request_counts: dict[str, tuple[int, float]] = {}


def rate_limit(limit: int, window_seconds: int) -> Callable:
    def check(request: Request) -> None:
        now = time.monotonic()
        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{request.url.path}"

        if len(_request_counts) > 5000:
            expired = [
                stored_key
                for stored_key, (_, expires_at) in _request_counts.items()
                if expires_at <= now
            ]
            for stored_key in expired:
                del _request_counts[stored_key]

        count, expires_at = _request_counts.get(key, (0, now + window_seconds))
        if expires_at <= now:
            count, expires_at = 0, now + window_seconds
        count += 1
        _request_counts[key] = (count, expires_at)

        if count > limit:
            retry_after = max(1, int(expires_at - now + 0.999))
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos. Espera un momento e inténtalo de nuevo.",
                headers={"Retry-After": str(retry_after)},
            )

    return check
