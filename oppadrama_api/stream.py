"""Resolver & proxy streaming.

Alur pemutaran di oppadrama.io:

    halaman episode -> <iframe src="https://vidara.to/e/<filecode>">
    vidara.to/e/<filecode> -> POST https://vidara.to/api/stream {filecode}
    -> {streaming_url: https://<cdn>/hls/<id>/master.m3u8?token=...}

Dari master.m3u8 diturunkan playlist kualitas dan segmen. Modul ini
menyediakan:

* ``resolve``       — ubah embed/URL apa pun menjadi info stream siap pakai
* ``playlist``      — ambil master/varian playlist
* ``rewrite_m3u8``  — arahkan semua URI di playlist ke proxy lokal
* ``proxy_segment`` — relay byte segmen (Range diteruskan)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin, urlparse

from . import config
from .http import UpstreamError, post_json, raw_get

logger = logging.getLogger(__name__)

VIDARA_API = "https://vidara.to/api/stream"
VIDARA_REFERER = "https://vidara.to/"

_EMBED_RE = re.compile(r"/e/([A-Za-z0-9_-]+)")
_FILECODE_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


def extract_filecode(value: str) -> Optional[str]:
    """Ambil filecode dari URL embed atau terima filecode mentah."""
    if not value:
        return None
    value = value.strip()
    m = _EMBED_RE.search(value)
    if m:
        return m.group(1)
    if _FILECODE_RE.match(value) and "/" not in value and ":" not in value:
        return value
    return None


def _host_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return urlparse(url).hostname


def resolve(embed: str) -> Dict[str, Any]:
    """Resolusi embed vidara -> info stream.

    Mengembalikan dict dengan ``streamingUrl`` (master m3u8), daftar
    ``qualities`` (diturunkan dari master), poster, dan subtitle.
    """
    embed = (embed or "").strip()
    if not embed:
        raise ValueError("Parameter 'url' / 'embed' wajib diisi")

    filecode = extract_filecode(embed)
    if not filecode:
        raise ValueError(
            "Tidak bisa membaca filecode. Kirim URL embed vidara "
            "(https://vidara.to/e/<filecode>) atau filecode mentah."
        )

    host = _host_of(embed) or "vidara.to"
    api = f"https://{host}/api/stream" if host not in ("vidara.to",) else VIDARA_API

    referer = embed if embed.startswith("http") else f"{VIDARA_REFERER}e/{filecode}"

    payload = {"filecode": filecode, "device": "web", "codecs": []}
    try:
        data = post_json(
            api,
            payload,
            headers={"Origin": f"https://{host}", "Referer": referer},
            ttl=config.STREAM_CACHE_TTL,
        )
    except UpstreamError as exc:
        # Fallback ke host utama bila host lain gagal.
        if api != VIDARA_API:
            data = post_json(
                VIDARA_API,
                payload,
                headers={"Origin": VIDARA_REFERER.rstrip("/"), "Referer": referer},
                ttl=config.STREAM_CACHE_TTL,
            )
        else:
            raise exc

    streaming_url = data.get("streaming_url")
    if not streaming_url:
        raise UpstreamError("Upstream tidak mengembalikan streaming_url")

    subtitles = []
    for sub in data.get("subtitles") or []:
        file_path = sub.get("file_path") or sub.get("file")
        if not file_path:
            continue
        subtitles.append(
            {
                "language": sub.get("language") or sub.get("label"),
                "file": file_path,
                "type": sub.get("type"),
                "default": bool(
                    (sub.get("language") or "").lower()
                    == (data.get("default_sub_lang") or "").lower()
                ),
            }
        )

    return {
        "filecode": filecode,
        "host": host,
        "embed": embed if embed.startswith("http") else f"{VIDARA_REFERER}e/{filecode}",
        "streamingUrl": streaming_url,
        "defaultSubtitleLang": data.get("default_sub_lang"),
        "subtitles": subtitles,
        "thumbnail": data.get("thumbnail"),
        "title": data.get("title") or None,
        "vastAds": data.get("vast_ads") or None,
    }


def _absolute_playlist_uri(base_url: str, uri: str) -> str:
    if uri.startswith("http://") or uri.startswith("https://"):
        return uri
    return urljoin(base_url, uri)


def parse_master(base_url: str, text: str) -> List[Dict[str, Any]]:
    """Baca varian kualitas dari master playlist."""
    qualities: List[Dict[str, Any]] = []
    lines = text.splitlines()
    pending: Dict[str, Any] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-STREAM-INF:"):
            attrs = line[len("#EXT-X-STREAM-INF:"):]
            resolution = re.search(r"RESOLUTION=(\d+x\d+)", attrs)
            bandwidth = re.search(r"BANDWIDTH=(\d+)", attrs)
            avg = re.search(r"AVERAGE-BANDWIDTH=(\d+)", attrs)
            pending = {
                "resolution": resolution.group(1) if resolution else None,
                "bandwidth": int(bandwidth.group(1)) if bandwidth else None,
                "averageBandwidth": int(avg.group(1)) if avg else None,
            }
        elif not line.startswith("#"):
            if pending:
                item = dict(pending)
                item["url"] = _absolute_playlist_uri(base_url, line)
                item["label"] = _quality_label(item.get("resolution"))
                qualities.append(item)
                pending = {}
    return qualities


def _quality_label(resolution: Optional[str]) -> Optional[str]:
    if not resolution:
        return None
    try:
        height = int(resolution.split("x")[1])
    except (IndexError, ValueError):
        return resolution
    mapping = {1080: "1080p", 720: "720p", 480: "480p", 360: "360p", 240: "240p"}
    return mapping.get(height, f"{height}p")


def is_master(text: str) -> bool:
    return "#EXT-X-STREAM-INF" in text


def _sorted_labels(qualities: List[Dict[str, Any]]) -> List[str]:
    """Label kualitas terurut dari tertinggi ke terendah."""

    def rank(label: str) -> int:
        digits = label.rstrip("p")
        return int(digits) if digits.isdigit() else 0

    labels = {q["label"] for q in qualities if q.get("label")}
    return sorted(labels, key=rank, reverse=True)


def resolve_full(embed: str, *, proxy_base: str = "/api/oppadrama-api") -> Dict[str, Any]:
    """Resolusi + baca master untuk melampirkan daftar kualitas siap pakai."""
    info = resolve(embed)
    master_url = info["streamingUrl"]
    try:
        resp = raw_get(master_url, headers={"Referer": VIDARA_REFERER})
        if resp.status_code == 200:
            text = resp.text
            if is_master(text):
                qualities = parse_master(master_url, text)
                for q in qualities:
                    q["proxyUrl"] = build_playlist_proxy_url(
                        proxy_base, q["url"], referer=VIDARA_REFERER
                    )
                info["qualities"] = qualities
                info["qualityLabels"] = _sorted_labels(qualities)
            else:
                info["qualities"] = []
                info["qualityLabels"] = []
            info["masterProxyUrl"] = build_playlist_proxy_url(
                proxy_base, master_url, referer=VIDARA_REFERER
            )
            info["isMaster"] = is_master(text)
    except UpstreamError as exc:
        info["qualities"] = []
        info["qualityLabels"] = []
        info["masterError"] = str(exc)

    return info


def build_playlist_proxy_url(proxy_base: str, url: str, *, referer: str = "") -> str:
    proxy_base = proxy_base.rstrip("/")
    q = f"?u={quote(url, safe='')}"
    if referer:
        q += f"&r={quote(referer, safe='')}"
    return f"{proxy_base}/stream/playlist{q}"


def build_segment_proxy_url(proxy_base: str, url: str, *, referer: str = "") -> str:
    proxy_base = proxy_base.rstrip("/")
    q = f"?u={quote(url, safe='')}"
    if referer:
        q += f"&r={quote(referer, safe='')}"
    return f"{proxy_base}/stream/seg{q}"


def rewrite_m3u8(
    base_url: str, text: str, *, proxy_base: str, referer: str = ""
) -> str:
    """Arahkan semua URI di playlist ke endpoint proxy kita."""
    out_lines: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue

        if stripped.startswith("#"):
            # Rewrite URI="..." di dalam tag (mis. EXT-X-KEY, EXT-X-MEDIA).
            def repl(match: re.Match) -> str:
                uri = match.group(1)
                target = _absolute_playlist_uri(base_url, uri)
                proxied = build_segment_proxy_url(
                    proxy_base, target, referer=referer
                )
                return f'URI="{proxied}"'

            out_lines.append(re.sub(r'URI="([^"]+)"', repl, line))
            continue

        target = _absolute_playlist_uri(base_url, stripped)
        if target.lower().split("?")[0].endswith(".m3u8"):
            out_lines.append(
                build_playlist_proxy_url(proxy_base, target, referer=referer)
            )
        else:
            out_lines.append(
                build_segment_proxy_url(proxy_base, target, referer=referer)
            )
    return "\n".join(out_lines)


def fetch_playlist(url: str, *, referer: str = "") -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        raise ValueError("URL playlist tidak valid")
    headers = {"Referer": referer} if referer else None
    resp = raw_get(url, headers=headers)
    if resp.status_code >= 400:
        raise UpstreamError(
            f"Upstream playlist mengembalikan {resp.status_code}", status=502
        )
    return resp.text


def proxy_segment(url: str, *, referer: str = "", range_header: Optional[str] = None):
    """Ambil segmen dari upstream dan kembalikan objek response requests."""
    if not url.startswith("http://") and not url.startswith("https://"):
        raise ValueError("URL segmen tidak valid")
    headers = {}
    if referer:
        headers["Referer"] = referer
    if range_header:
        headers["Range"] = range_header
    return raw_get(url, headers=headers, stream=True)


# Beberapa CDN menyamarkan segmen MPEG-TS sebagai .js dengan Content-Type
# application/javascript. Pemutar native (Safari) butuh MIME yang benar.
_SEGMENT_TYPES = {
    ".ts": "video/mp2t",
    ".js": "video/mp2t",
    ".m2ts": "video/mp2t",
    ".m4s": "video/mp4",
    ".mp4": "video/mp4",
    ".vtt": "text/vtt",
    ".key": "application/octet-stream",
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
}


def guess_segment_type(url: str, upstream_type: Optional[str]) -> str:
    """Tentukan Content-Type segmen: utamakan ekstensi bila upstream menyesatkan."""
    path = urlparse(url).path.lower()
    _, _, ext = path.rpartition(".")
    ext = f".{ext}" if ext else ""
    guessed = _SEGMENT_TYPES.get(ext)
    if guessed and (not upstream_type or "javascript" in upstream_type.lower()
                    or upstream_type.startswith("application/octet-stream")):
        return guessed
    return upstream_type or guessed or "application/octet-stream"
