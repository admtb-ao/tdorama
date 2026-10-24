"""Lapisan scraping: gabungkan HTTP client dengan parser."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from . import config, parsers
from .http import UpstreamError, get_text

logger = logging.getLogger(__name__)

BASE = config.BASE_URL

# Jenis taksonomi -> segmen URL.
TAXONOMY_PATHS = {
    "genre": "genres",
    "country": "country",
    "cast": "cast",
    "director": "director",
    "tag": "tag",
    "network": "network",
    "season": "season",
    "studio": "studio",
}

VALID_ORDER = {"title", "titlereverse", "update", "latest", "popular"}
VALID_STATUS = {"ongoing", "completed", "upcoming"}
VALID_TYPE = {"drama", "tv show", "anime", "movie", "special"}


def _page_url(path: str, page: int) -> str:
    url = f"{BASE}{path}"
    if page and page > 1:
        url = url.rstrip("/") + f"/page/{page}/"
    return url


def _validate_page(page: Any) -> int:
    try:
        n = int(page)
    except (TypeError, ValueError):
        raise ValueError("Parameter 'page' harus berupa angka")
    if n < 1:
        raise ValueError("Parameter 'page' minimal 1")
    if n > config.MAX_PAGE:
        raise ValueError(f"Parameter 'page' maksimal {config.MAX_PAGE}")
    return n


# --------------------------------------------------------------------------
# Beranda & daftar
# --------------------------------------------------------------------------

def get_home(page: Any = 1) -> Dict[str, Any]:
    n = _validate_page(page)
    url = BASE + "/" if n == 1 else f"{BASE}/page/{n}/"
    html = get_text(url)
    data = parsers.parse_home(html, url)
    data["page"] = n
    return data


def get_series(
    page: Any = 1,
    *,
    status: Optional[str] = None,
    type_: Optional[str] = None,
    order: Optional[str] = None,
    genre: Optional[List[str]] = None,
    country: Optional[List[str]] = None,
    season: Optional[List[str]] = None,
    studio: Optional[List[str]] = None,
    network: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Daftar series dengan filter (halaman /series)."""
    n = _validate_page(page)
    query: List[tuple] = []
    if status:
        status = status.strip().lower()
        if status and status not in VALID_STATUS:
            raise ValueError(
                "Status tidak valid. Pilihan: " + ", ".join(sorted(VALID_STATUS))
            )
        query.append(("status", status.capitalize() if status else ""))
    if type_:
        t = type_.strip().lower()
        if t and t not in VALID_TYPE:
            raise ValueError(
                "Tipe tidak valid. Pilihan: " + ", ".join(sorted(VALID_TYPE))
            )
        query.append(("type", t))
    if order:
        o = order.strip().lower()
        if o and o not in VALID_ORDER:
            raise ValueError(
                "Order tidak valid. Pilihan: " + ", ".join(sorted(VALID_ORDER))
            )
        query.append(("order", o))
    for key, values in (
        ("genre[]", genre),
        ("country[]", country),
        ("season[]", season),
        ("studio[]", studio),
        ("network[]", network),
    ):
        for v in values or []:
            if v and str(v).strip():
                query.append((key, str(v).strip()))

    qs = urlencode(query, doseq=True)
    if n > 1:
        query.append(("page", n))
        qs = urlencode(query, doseq=True)
    url = f"{BASE}/series/" + (f"?{qs}" if qs else "")
    html = get_text(url)
    return {
        "url": url,
        "page": n,
        "filters": {
            "status": status,
            "type": type_,
            "order": order,
            "genres": genre or [],
            "countries": country or [],
            "seasons": season or [],
            "studios": studio or [],
            "networks": network or [],
        },
        "items": parsers.parse_cards(html),
        "pagination": parsers.parse_pagination(html),
    }


def get_filter_options() -> Dict[str, Any]:
    html = get_text(f"{BASE}/series/")
    options = parsers.parse_filter_options(html)
    return {
        "filters": {
            k.replace("[]", ""): v for k, v in options.items()
        },
        "statuses": sorted(VALID_STATUS),
        "types": sorted(VALID_TYPE),
        "orders": sorted(VALID_ORDER),
    }


def get_recent_episodes(page: Any = 1) -> Dict[str, Any]:
    """Episode terbaru (tab utama halaman /series)."""
    n = _validate_page(page)
    url = _page_url("/series/", n) + "?order=update"
    html = get_text(url)
    return {
        "url": url,
        "page": n,
        "items": parsers.parse_cards(html),
        "pagination": parsers.parse_pagination(html),
    }


def get_list_mode(page: Any = 1) -> Dict[str, Any]:
    """Daftar A-Z mode teks (halaman /series/list-mode)."""
    n = _validate_page(page)
    url = _page_url("/series/list-mode/", n)
    html = get_text(url)
    # list-mode memakai markup .lista / .serieslist sederhana
    doc = parsers.soup(html)
    items: List[Dict[str, Any]] = []
    for a in doc.select(".lista a[href], .serieslist a.series[href]"):
        title = parsers.clean_text(a)
        url_item = parsers.absolute(a.get("href"))
        if not title or not url_item:
            continue
        items.append(
            {
                "title": title,
                "slug": parsers.slug_from_url(url_item, "any"),
                "url": url_item,
            }
        )
    return {
        "url": url,
        "page": n,
        "items": items,
        "pagination": parsers.parse_pagination(html),
    }


# --------------------------------------------------------------------------
# Detail
# --------------------------------------------------------------------------

def get_series_detail(slug: str) -> Dict[str, Any]:
    slug = (slug or "").strip().strip("/")
    if not slug:
        raise ValueError("Slug tidak boleh kosong")
    if "/" in slug:
        raise ValueError("Slug tidak valid")
    url = f"{BASE}/series/{slug}/"
    html = get_text(url)
    if parsers.is_not_found_page(html):
        raise UpstreamError(f"Series '{slug}' tidak ditemukan", status=404)
    return parsers.parse_series_detail(html, url)


def get_episode_detail(slug: str) -> Dict[str, Any]:
    slug = (slug or "").strip().strip("/")
    if not slug:
        raise ValueError("Slug tidak boleh kosong")
    if "/" in slug:
        raise ValueError("Slug tidak valid")
    url = f"{BASE}/{slug}/"
    html = get_text(url)
    if parsers.is_not_found_page(html):
        raise UpstreamError(f"Episode '{slug}' tidak ditemukan", status=404)
    return parsers.parse_episode_detail(html, url)


def get_series_episodes(slug: str) -> Dict[str, Any]:
    detail = get_series_detail(slug)
    return {
        "slug": detail.get("slug"),
        "title": detail.get("title"),
        "url": detail.get("url"),
        "total": detail.get("episodeCount"),
        "episodes": detail.get("episodes", []),
    }


# --------------------------------------------------------------------------
# Pencarian
# --------------------------------------------------------------------------

def search(query: str, page: Any = 1) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        raise ValueError("Parameter 'q' tidak boleh kosong")
    n = _validate_page(page)
    params = {"s": q}
    if n > 1:
        params["page"] = n
    url = f"{BASE}/?{urlencode(params)}"
    html = get_text(url)
    items = parsers.parse_cards(html)
    doc = parsers.soup(html)
    label = None
    h1 = doc.select_one(".releases h1")
    if h1:
        label = parsers.clean_text(h1)
    return {
        "query": q,
        "url": url,
        "page": n,
        "resultLabel": label,
        "count": len(items),
        "items": items,
        "pagination": parsers.parse_pagination(html),
    }


# --------------------------------------------------------------------------
# Taksonomi
# --------------------------------------------------------------------------

def get_taxonomy_list(kind: str, page: Any = 1) -> Dict[str, Any]:
    """Daftar series per taksonomi: genre/country/cast/director/tag/network/season/studio."""
    key = (kind or "").strip().lower()
    if key not in TAXONOMY_PATHS:
        raise ValueError(
            "Jenis taksonomi tidak valid. Pilihan: " + ", ".join(sorted(TAXONOMY_PATHS))
        )
    return {"kinds": sorted(TAXONOMY_PATHS)}


def get_taxonomy_archive(kind: str, slug: str, page: Any = 1) -> Dict[str, Any]:
    key = (kind or "").strip().lower()
    if key not in TAXONOMY_PATHS:
        raise ValueError(
            "Jenis taksonomi tidak valid. Pilihan: " + ", ".join(sorted(TAXONOMY_PATHS))
        )
    term = (slug or "").strip().strip("/")
    if not term or "/" in term:
        raise ValueError("Slug taksonomi tidak valid")
    n = _validate_page(page)
    path = f"/{TAXONOMY_PATHS[key]}/{term}/"
    url = _page_url(path, n)
    html = get_text(url)
    doc = parsers.soup(html)
    h1 = doc.select_one(".releases h1, .releases h2, .releases h3")
    return {
        "kind": key,
        "slug": term,
        "name": parsers.clean_text(h1),
        "url": url,
        "page": n,
        "items": parsers.parse_cards(html),
        "pagination": parsers.parse_pagination(html),
    }


# --------------------------------------------------------------------------
# Domain
# --------------------------------------------------------------------------

def get_domains() -> Dict[str, Any]:
    """Info domain aktif dan kandidat cadangan."""
    active = None
    ok = False
    try:
        html = get_text(BASE + "/", use_cache=False)
        doc = parsers.soup(html)
        title = doc.select_one("title")
        active = {
            "url": BASE,
            "title": parsers.clean_text(title),
            "reachable": True,
        }
        ok = True
    except UpstreamError as exc:
        active = {"url": BASE, "reachable": False, "error": str(exc)}

    candidates = []
    for candidate in config.DOMAIN_CANDIDATES:
        candidates.append({"url": candidate, "active": candidate == BASE})

    return {
        "active": active,
        "baseUrl": BASE,
        "candidates": candidates,
        "ok": ok,
    }
