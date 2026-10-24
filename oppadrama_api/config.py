"""Konfigurasi runtime oppadrama-api."""

import os

# Domain upstream. Bisa dioverride lewat environment variable bila domain
# utama berganti (situs ini beberapa kali pindah domain).
BASE_URL = os.getenv("OPPADRAMA_BASE_URL", "https://oppadrama.io")

# Kandidat domain cadangan yang dilaporkan oleh /domains.
DOMAIN_CANDIDATES = [
    d.strip()
    for d in os.getenv(
        "OPPADRAMA_DOMAINS", "https://oppadrama.io"
    ).split(",")
    if d.strip()
]

USER_AGENT = os.getenv(
    "OPPADRAMA_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
)

# Timeout HTTP (detik).
REQUEST_TIMEOUT = float(os.getenv("OPPADRAMA_TIMEOUT", "25"))

# TTL cache (detik) untuk halaman HTML.
CACHE_TTL = int(os.getenv("OPPADRAMA_CACHE_TTL", "300"))
# TTL khusus untuk URL stream HLS (token biasanya berlaku ~8 jam).
STREAM_CACHE_TTL = int(os.getenv("OPPADRAMA_STREAM_CACHE_TTL", "600"))

# Retry.
MAX_RETRIES = int(os.getenv("OPPADRAMA_MAX_RETRIES", "3"))

# Batas halaman yang boleh diminta klien.
MAX_PAGE = int(os.getenv("OPPADRAMA_MAX_PAGE", "500"))

# Ukuran maksimum byte yang direlay endpoint segmen (per request).
SEGMENT_CHUNK = 512 * 1024
