"""Klien HTTP dengan cache TTL dan retry sederhana."""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional, Tuple

import requests

from . import config

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }
)

_cache: Dict[str, Tuple[float, object]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: str):
    with _cache_lock:
        item = _cache.get(key)
    if not item:
        return None
    expires_at, value = item
    if expires_at < time.time():
        with _cache_lock:
            _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value, ttl: int) -> None:
    with _cache_lock:
        _cache[key] = (time.time() + ttl, value)
        # Buang entri basi agar cache tidak tumbuh tanpa batas.
        if len(_cache) > 500:
            now = time.time()
            for k in [k for k, (exp, _) in _cache.items() if exp < now]:
                _cache.pop(k, None)


def clear_cache() -> int:
    """Kosongkan cache. Mengembalikan jumlah entri yang dibuang."""
    with _cache_lock:
        n = len(_cache)
        _cache.clear()
    return n


def upcoming_cache_info() -> Dict[str, int]:
    with _cache_lock:
        now = time.time()
        alive = sum(1 for exp, _ in _cache.values() if exp >= now)
        return {"entries": len(_cache), "valid": alive, "ttl": config.CACHE_TTL}


class UpstreamError(RuntimeError):
    """Upstream tidak bisa dihubungi atau mengembalikan status non-200."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


def get_text(
    url: str,
    *,
    ttl: Optional[int] = None,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    use_cache: bool = True,
) -> str:
    """Ambil halaman sebagai teks, dengan cache TTL dan retry."""
    key = f"GET {url} {sorted((params or {}).items())}"
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

    last_error: Optional[Exception] = None
    for attempt in range(config.MAX_RETRIES):
        try:
            resp = _session.get(
                url,
                params=params,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT,
            )
            if resp.status_code == 404:
                raise UpstreamError(f"Tidak ditemukan: {url}", status=404)
            resp.raise_for_status()
            text = resp.text
            if use_cache:
                _cache_set(key, text, ttl or config.CACHE_TTL)
            return text
        except UpstreamError:
            raise
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 502
            raise UpstreamError(
                f"Upstream mengembalikan {status} untuk {url}", status=status
            ) from exc
        except requests.RequestException as exc:
            last_error = exc
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(0.6 * (attempt + 1))
                continue
            break

    raise UpstreamError(f"Gagal menghubungi upstream: {last_error}")


def post_json(
    url: str,
    payload: dict,
    *,
    headers: Optional[dict] = None,
    ttl: Optional[int] = None,
    use_cache: bool = True,
) -> dict:
    """POST JSON dan kembalikan objek JSON, dengan cache TTL opsional."""
    key = f"POST {url} {sorted(payload.items())}"
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

    merged = {
        "User-Agent": config.USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        merged.update(headers)

    last_error: Optional[Exception] = None
    for attempt in range(config.MAX_RETRIES):
        try:
            resp = _session.post(
                url,
                json=payload,
                headers=merged,
                timeout=config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                _cache_set(key, data, ttl or config.CACHE_TTL)
            return data
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 502
            raise UpstreamError(
                f"Upstream streaming mengembalikan {status}; "
                "server mungkin sudah kedaluwarsa atau tidak valid.",
                status=400 if status in (400, 404, 422) else 502,
            ) from exc
        except requests.RequestException as exc:
            last_error = exc
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(0.6 * (attempt + 1))
                continue
            break
        except ValueError as exc:  # JSON tidak valid
            raise UpstreamError(f"Respons bukan JSON: {exc}") from exc

    raise UpstreamError(f"Gagal menghubungi upstream: {last_error}")


def raw_get(url: str, *, headers: Optional[dict] = None, stream: bool = False):
    """GET mentah (tanpa cache) untuk playlist dan segmen HLS."""
    merged = {"User-Agent": config.USER_AGENT}
    if headers:
        merged.update(headers)
    try:
        return _session.get(
            url,
            headers=merged,
            timeout=config.REQUEST_TIMEOUT,
            stream=stream,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise UpstreamError(f"Gagal menghubungi upstream: {exc}") from exc
