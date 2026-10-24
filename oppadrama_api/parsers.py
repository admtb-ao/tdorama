"""Parser HTML untuk oppadrama.io.

Semua fungsi di sini murni: menerima string HTML dan mengembalikan struktur
data. Tidak ada request jaringan di modul ini.
"""

from __future__ import annotations

import base64
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, unquote

from bs4 import BeautifulSoup, Tag

from . import config

BASE = config.BASE_URL


# --------------------------------------------------------------------------
# Helper umum
# --------------------------------------------------------------------------

def soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:  # pragma: no cover - fallback bila lxml absen
        return BeautifulSoup(html, "html.parser")


def is_not_found_page(html: str) -> bool:
    """Situs mengalihkan slug yang tidak ada ke beranda.

    Deteksi: halaman tanpa wadah detail dan memuat penanda beranda.
    """
    doc = soup(html)
    if doc.select_one(".bigcontent .infox") or doc.select_one(".megavid"):
        return False
    if doc.select_one("article.bs") and doc.select_one(".latesthome"):
        return True
    if doc.select_one(".releases.latesthome") and not doc.select_one("h1.entry-title"):
        return True
    return False


def absolute(url: Optional[str]) -> Optional[str]:
    """Jadikan URL absolut relatif terhadap BASE_URL."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("#") or url.startswith("javascript:"):
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return urljoin(BASE + "/", url.lstrip("/"))


def slug_from_url(url: Optional[str], kind: str = "series") -> Optional[str]:
    """Ambil slug dari URL.

    ``kind`` menentukan segmen yang diharapkan:
    - ``series``  -> /series/<slug>/
    - ``any``     -> segmen terakhir apa pun (dipakai untuk episode).
    """
    if not url:
        return None
    path = urlparse(url).path.strip("/")
    if not path:
        return None
    parts = [p for p in path.split("/") if p]
    if kind == "series":
        if "series" in parts:
            idx = parts.index("series")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return None
    return parts[-1] if parts else None


def clean_text(node: Optional[Tag]) -> Optional[str]:
    if node is None:
        return None
    text = node.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    m = re.search(r"\d+", value)
    return int(m.group(0)) if m else None


def _float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", value)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Kartu (article.bs) — dipakai di home, arsip, pencarian
# --------------------------------------------------------------------------

def parse_card(article: Tag) -> Optional[Dict[str, Any]]:
    link = article.select_one("a.tip") or article.select_one("a[href]")
    if not link or not link.get("href"):
        return None
    url = absolute(link["href"])
    title = link.get("title") or clean_text(article.select_one("h2"))
    title = (title or "").strip() or None
    slug = slug_from_url(url, "any")

    img = article.select_one("img")
    poster = None
    if img:
        poster = absolute(img.get("src") or img.get("data-src"))

    type_node = article.select_one(".typez")
    type_label = clean_text(type_node) if type_node else None

    epx = clean_text(article.select_one(".epx"))
    sub = clean_text(article.select_one(".sb"))
    timeago = clean_text(article.select_one(".timeago"))

    status = epx
    episode = None
    if epx:
        m = re.search(r"ep\s*\.?\s*(\d+)", epx, re.I)
        if m:
            episode = int(m.group(1))
    finished = bool(re.search(r"\bend\b|tamat|completed", f"{epx or ''} {title or ''}", re.I))
    is_movie = bool(type_label and type_label.lower() == "movie")
    if is_movie:
        status = "Movie"
    elif episode is not None:
        status = "Completed" if finished else "Ongoing"

    return {
        "title": title,
        "slug": slug,
        "url": url,
        "type": type_label,
        "poster": poster,
        "episode": episode,
        "episodeLabel": epx,
        "sub": sub,
        "status": status,
        "updatedAgo": timeago,
        "movieId": link.get("rel") if isinstance(link.get("rel"), str) else (
            link.get("rel")[0] if link.get("rel") else None
        ),
    }


def parse_cards(html: str) -> List[Dict[str, Any]]:
    doc = soup(html)
    cards: List[Dict[str, Any]] = []
    for article in doc.select("article.bs"):
        card = parse_card(article)
        if card:
            cards.append(card)
    return cards


def parse_pagination(html: str) -> Dict[str, Any]:
    doc = soup(html)
    box = doc.select_one("div.pagination")
    result: Dict[str, Any] = {
        "currentPage": 1,
        "totalPages": 1,
        "hasNext": False,
        "nextPage": None,
        "prevPage": None,
    }
    if not box:
        # Arsip "series" memakai tombol "Selanjutnya" (?page=N).
        sel = doc.select_one(".hpage a[href*='page=']")
        if sel:
            result["hasNext"] = True
            result["nextPage"] = 2
            result["totalPages"] = 2
        return result

    current = box.select_one("span.page-numbers.current")
    numbers = []
    for a in box.select("a.page-numbers"):
        n = _int(a.get_text())
        if n:
            numbers.append(n)
    for span in box.select("span.page-numbers"):
        n = _int(span.get_text())
        if n:
            numbers.append(n)

    if current:
        result["currentPage"] = _int(current.get_text()) or 1
    if numbers:
        result["totalPages"] = max(numbers)

    prev_link = box.select_one("a.prev.page-numbers")
    if prev_link:
        # Tautan "Previous" tanpa nomor halaman berarti kembali ke halaman 1.
        result["prevPage"] = _page_from_href(prev_link.get("href")) or 1

    nxt = box.select_one("a.next.page-numbers")
    if nxt:
        result["nextPage"] = _page_from_href(nxt.get("href"))
        if result["nextPage"] is None:
            result["nextPage"] = result["currentPage"] + 1
        result["hasNext"] = True

    if (
        not result["hasNext"]
        and result["totalPages"]
        and result["currentPage"] < result["totalPages"]
    ):
        result["hasNext"] = True
        result["nextPage"] = result["currentPage"] + 1
    return result


def _page_from_href(href: Optional[str]) -> Optional[int]:
    if not href:
        return None
    m = re.search(r"/page/(\d+)", href)
    if m:
        return int(m.group(1))
    m = re.search(r"[?&]page=(\d+)", href)
    if m:
        return int(m.group(1))
    return None


# --------------------------------------------------------------------------
# Blok metadata "spe" pada halaman detail
# --------------------------------------------------------------------------

_SPE_LABELS = {
    "status": "status",
    "network": "network",
    "durasi": "duration",
    "negara": "country",
    "tipe": "type",
    "episode": "totalEpisodes",
    "sutradara": "director",
    "artis": "cast",
    "diposting oleh": "author",
    "dirilis": "released",
    "diperbarui pada": "updated",
    "rating": "rating",
    "studio": "studio",
    "musim": "season",
    "season": "season",
}


def _parse_spe(infox: Tag) -> Dict[str, Any]:
    """Parse div.spe menjadi dict + representasi bertipe."""
    out: Dict[str, Any] = {}
    labels: List[Dict[str, str]] = []
    spe = infox.select_one(".spe")
    if not spe:
        return out

    for span in spe.find_all("span", recursive=False):
        b = span.find("b")
        if not b:
            continue
        label = clean_text(b)
        if not label:
            continue
        label = label.rstrip(":").strip()
        key = _SPE_LABELS.get(label.lower())
        if not key:
            continue

        # Nilai: hapus elemen <b>, sisanya jadi teks/tautan.
        clone = span
        raw_parts = []
        for child in span.children:
            if isinstance(child, Tag) and child.name == "b":
                continue
            raw_parts.append(child)

        links = [
            {
                "name": clean_text(a),
                "slug": slug_from_url(absolute(a.get("href")), "any"),
                "url": absolute(a.get("href")),
            }
            for a in span.find_all("a")
        ]

        text = " ".join(
            p.get_text(" ", strip=True) if isinstance(p, Tag) else str(p)
            for p in raw_parts
        )
        text = re.sub(r"\s+", " ", text).strip(" ,") or None

        if key in ("director", "cast", "network", "country", "studio"):
            out[key] = links if len(links) > 1 else (links[0] if links else text)
        elif key == "totalEpisodes":
            out[key] = _int(text)
        else:
            out[key] = text
        labels.append({"label": label, "key": key, "value": text})

    out["_meta"] = labels
    return out


def _parse_rating(thumbook: Tag) -> Optional[Dict[str, Any]]:
    node = thumbook.select_one(".rating")
    if not node:
        return None
    agg = node.select_one("[itemprop='aggregateRating']")
    value = None
    count = None
    if agg:
        v = agg.select_one("meta[itemprop='ratingValue']")
        c = agg.select_one("meta[itemprop='ratingCount']")
        value = v.get("content") if v else None
        count = c.get("content") if c else None
    if value is None:
        strong = node.find("strong")
        value = clean_text(strong)
    return {
        "value": _float(value),
        "count": _int(count),
        "label": clean_text(node.find("strong")),
    }


# --------------------------------------------------------------------------
# Halaman detail series
# --------------------------------------------------------------------------

def parse_series_detail(html: str, url: Optional[str] = None) -> Dict[str, Any]:
    doc = soup(html)

    infox = doc.select_one(".bigcontent .infox") or doc.select_one(".infox")
    if not infox:
        raise ValueError("Struktur halaman detail tidak dikenali")

    title_node = infox.select_one("h1.entry-title") or infox.find("h1")
    title = clean_text(title_node)
    alt = clean_text(infox.select_one(".alter"))

    thumbook = doc.select_one(".thumbook")
    poster = None
    if thumbook:
        img = thumbook.select_one("img")
        if img:
            poster = absolute(img.get("src"))

    genres = []
    genxed = infox.select_one(".genxed")
    if genxed:
        for a in genxed.find_all("a"):
            genres.append(
                {
                    "name": clean_text(a),
                    "slug": slug_from_url(absolute(a.get("href")), "any"),
                    "url": absolute(a.get("href")),
                }
            )

    spe = _parse_spe(infox)
    meta_labels = spe.pop("_meta", [])

    description = clean_text(infox.select_one(".desc"))
    tagline = clean_text(infox.select_one(".mindesc"))

    synopsis = None
    synp = doc.select_one(".bixbox.synp .entry-content")
    if synp:
        synopsis = re.sub(r"\s+\n", "\n", synp.get_text("\n", strip=True)).strip() or None

    tags = []
    for a in doc.select(".bottom.tags a"):
        tags.append(
            {
                "name": clean_text(a),
                "slug": slug_from_url(absolute(a.get("href")), "any"),
                "url": absolute(a.get("href")),
            }
        )

    episodes: List[Dict[str, Any]] = []
    for li in doc.select(".eplister li"):
        a = li.select_one("a[href]")
        if not a:
            continue
        ep_url = absolute(a.get("href"))
        num = _int(clean_text(a.select_one(".epl-num")))
        episodes.append(
            {
                "number": num,
                "title": clean_text(a.select_one(".epl-title")),
                "date": clean_text(a.select_one(".epl-date")),
                "slug": slug_from_url(ep_url, "any"),
                "url": ep_url,
            }
        )

    rating = _parse_rating(thumbook) if thumbook else None

    breadcrumb = [
        clean_text(a) for a in doc.select(".breadcrumb a") if clean_text(a)
    ]

    slug = slug_from_url(url or "", "series") if url else None
    if not slug:
        canonical = doc.select_one("link[rel='canonical']")
        if canonical:
            slug = slug_from_url(canonical.get("href"), "series")

    return {
        "title": title,
        "altTitle": alt,
        "slug": slug,
        "url": url,
        "poster": poster,
        "tagline": tagline,
        "description": description,
        "synopsis": synopsis,
        "genres": genres,
        "tags": tags,
        "rating": rating,
        "breadcrumb": breadcrumb,
        "meta": spe,
        "metaLabels": meta_labels,
        "episodes": episodes,
        "episodeCount": len(episodes),
    }


# --------------------------------------------------------------------------
# Halaman episode
# --------------------------------------------------------------------------

def parse_mirrors(html: str) -> List[Dict[str, Any]]:
    """Decode opsi select.mirror (base64 berisi iframe)."""
    doc = soup(html)
    select = doc.select_one("select.mirror")
    if not select:
        return []

    mirrors: List[Dict[str, Any]] = []
    for opt in select.find_all("option"):
        value = (opt.get("value") or "").strip()
        if not value:
            continue
        try:
            decoded = base64.b64decode(value).decode("utf-8", "replace")
        except Exception:
            continue
        m = re.search(r'src=["\']([^"\']+)["\']', decoded)
        embed = m.group(1) if m else None
        if not embed:
            continue
        host = urlparse(embed).hostname
        label = clean_text(opt)
        mirrors.append(
            {
                "name": label or host,
                "host": host,
                "embed": absolute(embed),
                "index": _int(opt.get("data-index") or str(len(mirrors) + 1)),
                "html": decoded.strip(),
            }
        )
    return mirrors


def parse_episode_detail(html: str, url: Optional[str] = None) -> Dict[str, Any]:
    doc = soup(html)

    title = None
    h1 = doc.select_one("h1.entry-title") or doc.select_one("h1")
    if h1:
        title = clean_text(h1)

    poster = None
    img = doc.select_one(".megavid .tb img") or doc.select_one(".thumb img")
    if img:
        poster = absolute(img.get("src") or img.get("data-src"))

    # Tipe drama/movie.
    epx = clean_text(doc.select_one(".megavid .epx"))
    content_type = epx.split()[0] if epx else None

    # Tanggal + series induk dari blok .year
    released = None
    series_url = None
    series_title = None
    year_node = doc.select_one(".megavid .year")
    if year_node:
        t = year_node.find("time")
        if t:
            released = {
                "text": clean_text(t),
                "iso": t.get("datetime"),
            }
        series_link = year_node.find("a", href=re.compile(r"/series/"))
        if series_link:
            series_url = absolute(series_link.get("href"))
            series_title = clean_text(series_link)

    author_node = doc.select_one(".megavid .entry-author-name")
    author = clean_text(author_node) if author_node else None

    iframe = doc.select_one(".player-embed iframe")
    default_embed = absolute(iframe.get("src")) if iframe else None
    default_host = urlparse(default_embed).hostname if default_embed else None

    mirrors = parse_mirrors(html)

    # Download links: tabel .dlbox
    downloads: List[Dict[str, Any]] = []
    for li in doc.select(".dlbox ul li"):
        if "head" in (li.get("class") or []):
            continue
        server_node = li.select_one(".q")
        quality_node = li.select_one(".w")
        a = li.select_one(".e a[href], a[href]")
        if not a:
            continue
        server_text = clean_text(server_node)
        if server_text:
            server_text = re.sub(r"^Download\s+", "", server_text).strip()
        downloads.append(
            {
                "server": server_text,
                "quality": clean_text(quality_node),
                "url": absolute(a.get("href")),
            }
        )

    prev_url = next_url = None
    nav = doc.select_one(".naveps.bignav")
    if nav:
        prev_a = nav.select_one(".nvs a[rel='prev']")
        if prev_a:
            prev_url = absolute(prev_a.get("href"))
        nxt_a = nav.select_one(".nvs a[rel='next']")
        if nxt_a:
            next_url = absolute(nxt_a.get("href"))
        if not next_url:
            for a in nav.select(".nvs a"):
                if clean_text(a) and "next" in (clean_text(a) or "").lower():
                    next_url = absolute(a.get("href"))

    description = None
    infx = doc.select_one(".bixbox.infx p")
    if infx:
        description = clean_text(infx)

    slug = slug_from_url(url or "", "any") if url else None
    if not slug:
        canonical = doc.select_one("link[rel='canonical']")
        if canonical:
            slug = slug_from_url(canonical.get("href"), "any")

    return {
        "title": title,
        "slug": slug,
        "url": url,
        "type": content_type,
        "poster": poster,
        "released": released,
        "updatedAgo": clean_text(doc.select_one(".year")),
        "author": author,
        "series": {
            "title": series_title,
            "slug": slug_from_url(series_url, "series") if series_url else None,
            "url": series_url,
        },
        "defaultEmbed": default_embed,
        "defaultHost": default_host,
        "mirrors": mirrors,
        "downloads": downloads,
        "prev": prev_url,
        "next": next_url,
        "description": description,
    }


# --------------------------------------------------------------------------
# Beranda
# --------------------------------------------------------------------------

def _parse_ongoingseries(doc: BeautifulSoup) -> List[Dict[str, Any]]:
    items = []
    for a in doc.select(".ongoingseries ul li a"):
        title_span = a.select_one(".l")
        ep_span = a.select_one(".r")
        name = clean_text(title_span)
        if not name:
            continue
        # Buang ikon di dalam .l
        if title_span:
            icon = title_span.find("i")
            if icon:
                icon.extract()
            name = clean_text(title_span)
        items.append(
            {
                "title": name,
                "slug": slug_from_url(absolute(a.get("href")), "any"),
                "url": absolute(a.get("href")),
                "episodeLabel": clean_text(ep_span),
            }
        )
    return items


def _parse_series_list(doc: BeautifulSoup) -> List[Dict[str, Any]]:
    items = []
    for li in doc.select(".serieslist ul li"):
        a = li.select_one("img") or li.select_one("a.series")
        link = li.select_one("h4 a.series") or li.select_one("a.series")
        if not link:
            continue
        img = li.select_one("img")
        genre_links = [
            {"name": clean_text(g), "slug": slug_from_url(absolute(g.get("href")), "any")}
            for g in li.select(".leftseries a[rel='tag']")
        ]
        spans = [clean_text(s) for s in li.select(".leftseries > span") if clean_text(s)]
        items.append(
            {
                "title": clean_text(link),
                "slug": slug_from_url(absolute(link.get("href")), "series"),
                "url": absolute(link.get("href")),
                "poster": absolute(img.get("src")) if img else None,
                "genres": genre_links,
                "info": spans,
            }
        )
    return items


def parse_home(html: str, url: Optional[str] = None) -> Dict[str, Any]:
    doc = soup(html)

    sections: List[Dict[str, Any]] = []

    # "Rilisan Terbaru" / grid utama
    latest_cards = parse_cards(html)
    # Judul section dari releases pertama bila ada.
    for box in doc.select(".bixbox"):
        header = box.select_one(".releases h1, .releases h3")
        label = clean_text(header)
        if not label:
            continue
        if box.select(".series-gen"):
            tabs = []
            for li in box.select(".series-gen .nav-tabs li"):
                tab_id = None
                a = li.find("a")
                if a and a.get("href"):
                    tab_id = a["href"].lstrip("#")
                pane = box.select_one(f"#{tab_id}") if tab_id else None
                cards = []
                if pane:
                    for article in pane.select("article.bs"):
                        card = parse_card(article)
                        if card:
                            cards.append(card)
                tabs.append(
                    {
                        "name": clean_text(li),
                        "id": tab_id,
                        "items": cards,
                    }
                )
            sections.append({"title": label, "type": "tabs", "items": tabs})
        elif box.select(".ongoingseries"):
            sections.append(
                {
                    "title": label,
                    "type": "ongoing",
                    "items": _parse_ongoingseries(box),
                }
            )
        elif box.select(".serieslist"):
            sections.append(
                {
                    "title": label,
                    "type": "serieslist",
                    "items": _parse_series_list(box),
                }
            )
        elif box.select_one("article.bs"):
            items = []
            for article in box.select("article.bs"):
                card = parse_card(article)
                if card:
                    items.append(card)
            sections.append({"title": label, "type": "cards", "items": items})

    # Sidebar: "Sedang Tayang" dan "Judul Drama/Series Baru"
    for section in doc.select("#sidebar .section"):
        header = section.select_one(".releases h1, .releases h2, .releases h3")
        label = clean_text(header)
        if not label:
            continue
        if section.select(".ongoingseries"):
            sections.append(
                {
                    "title": label,
                    "type": "ongoing",
                    "items": _parse_ongoingseries(section),
                }
            )
        elif section.select(".serieslist"):
            sections.append(
                {
                    "title": label,
                    "type": "serieslist",
                    "items": _parse_series_list(section),
                }
            )

    return {
        "url": url or BASE + "/",
        "latest": latest_cards,
        "sections": sections,
        "pagination": parse_pagination(html),
    }


# --------------------------------------------------------------------------
# Filter / taksonomi
# --------------------------------------------------------------------------

def parse_filter_options(html: str) -> Dict[str, List[Dict[str, str]]]:
    """Ambil opsi filter dari form .filters di halaman /series."""
    doc = soup(html)
    form = doc.select_one("form.filters")
    if not form:
        return {}
    out: Dict[str, List[Dict[str, str]]] = {}
    for inp in form.select("input[name]"):
        name = inp.get("name")
        if not name:
            continue
        value = inp.get("value") or ""
        label = ""
        inp_id = inp.get("id")
        if inp_id:
            lab = form.select_one(f"label[for='{inp_id}']")
            if lab:
                label = clean_text(lab) or ""
        out.setdefault(name, []).append({"name": label or value, "slug": value})
    return out


def parse_taxonomy_terms(html: str) -> List[Dict[str, Any]]:
    """Parse daftar istilah dari halaman indeks taksonomi (mis. /genres)."""
    doc = soup(html)
    terms = []
    for a in doc.select(".taxindex li a, .az-list li a"):
        name = clean_text(a)
        if not name:
            continue
        terms.append(
            {
                "name": name,
                "slug": slug_from_url(absolute(a.get("href")), "any"),
                "url": absolute(a.get("href")),
                "count": _int(a.get("data-count")) if a.get("data-count") else None,
            }
        )
    return terms
