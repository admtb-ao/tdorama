"""Skema OpenAPI 3.0 untuk oppadrama-api."""

from __future__ import annotations

from typing import Any, Dict

from . import __version__, config


def _err(desc: str) -> Dict[str, Any]:
    return {
        "description": desc,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Error"}
            }
        },
    }


PAGINATION = {
    "type": "object",
    "properties": {
        "currentPage": {"type": "integer", "example": 1},
        "totalPages": {"type": "integer", "example": 42},
        "hasNext": {"type": "boolean", "example": True},
        "nextPage": {"type": "integer", "nullable": True, "example": 2},
    },
}

CARD = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "nullable": True},
        "slug": {"type": "string", "nullable": True},
        "url": {"type": "string", "nullable": True},
        "type": {"type": "string", "nullable": True, "example": "Drama"},
        "poster": {"type": "string", "nullable": True},
        "episode": {"type": "integer", "nullable": True},
        "episodeLabel": {"type": "string", "nullable": True, "example": "Ep 8"},
        "sub": {"type": "string", "nullable": True, "example": "Sub"},
        "status": {"type": "string", "nullable": True, "example": "Ongoing"},
        "updatedAgo": {"type": "string", "nullable": True, "example": "6 hours lalu"},
        "movieId": {"type": "string", "nullable": True},
    },
}

EPISODE = {
    "type": "object",
    "properties": {
        "number": {"type": "integer", "nullable": True},
        "title": {"type": "string", "nullable": True},
        "date": {"type": "string", "nullable": True},
        "slug": {"type": "string", "nullable": True},
        "url": {"type": "string", "nullable": True},
    },
}

MIRROR = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "nullable": True},
        "host": {"type": "string", "nullable": True},
        "embed": {"type": "string", "nullable": True},
        "index": {"type": "integer", "nullable": True},
    },
}

STREAM = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean", "example": True},
        "data": {
            "type": "object",
            "properties": {
                "filecode": {"type": "string"},
                "embed": {"type": "string"},
                "streamingUrl": {
                    "type": "string",
                    "description": "Master HLS m3u8 dari upstream",
                },
                "isMaster": {"type": "boolean"},
                "qualityLabels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "example": ["1080p", "720p", "480p"],
                },
                "qualities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "nullable": True},
                            "resolution": {"type": "string", "nullable": True},
                            "bandwidth": {"type": "integer", "nullable": True},
                            "url": {"type": "string"},
                            "proxyUrl": {
                                "type": "string",
                                "description": "URL playlist lewat proxy API",
                            },
                        },
                    },
                },
                "masterProxyUrl": {
                    "type": "string",
                    "description": "Playlist master lewat proxy API (siap untuk hls.js)",
                },
                "subtitles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "language": {"type": "string", "nullable": True},
                            "file": {"type": "string"},
                            "type": {"type": "integer", "nullable": True},
                            "default": {"type": "boolean"},
                        },
                    },
                },
                "thumbnail": {"type": "string", "nullable": True},
                "defaultSubtitleLang": {"type": "string", "nullable": True},
            },
        },
    },
}


def build_spec(proxy_base: str = "/api/oppadrama-api") -> Dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "oppadrama-api",
            "version": __version__,
            "description": (
                "REST API scraper untuk **OPPADRAMA** (oppadrama.io) — drama, "
                "series, dan film subtitle Indonesia.\n\n"
                "Menyediakan beranda, daftar & filter series, detail lengkap "
                "(metadata, cast, genre, rating, sinopsis), daftar episode, "
                "server streaming HLS (1080p/720p/480p), link download, "
                "jadwal, genre, dan pencarian.\n\n"
                "Endpoint `/stream`, `/stream/playlist`, dan `/stream/seg` "
                "membuat hasil scraping langsung bisa diputar di player "
                "(hls.js / Video.js) tanpa terkena pembatasan referer.\n\n"
                "> ⚠️ Proyek edukasi. API ini tidak menghosting konten apa pun, "
                "hanya membaca halaman publik dan meneruskan tautan pihak ketiga."
            ),
            "license": {"name": "MIT"},
        },
        "servers": [{"url": proxy_base, "description": "Gateway"}],
        "tags": [
            {"name": "oppadrama", "description": "Drama & series OPPADRAMA sub indo"}
        ],
        "paths": {
            "/home": {
                "get": {
                    "summary": "Beranda — rilis terbaru, rekomendasi, sidebar",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "schema": {"type": "integer", "default": 1},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Data beranda"},
                        "400": _err("Parameter tidak valid"),
                        "502": _err("Upstream gagal"),
                    },
                }
            },
            "/series": {
                "get": {
                    "summary": "Daftar series + filter (status/tipe/genre/negara/urutan)",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["ongoing", "completed", "upcoming"],
                            },
                        },
                        {
                            "name": "type",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["drama", "tv show", "anime", "movie", "special"],
                            },
                        },
                        {
                            "name": "order",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["title", "titlereverse", "update", "latest", "popular"],
                            },
                        },
                        {
                            "name": "genre",
                            "in": "query",
                            "description": "Boleh diulang. Contoh: genre=drama&genre=romance",
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                        {
                            "name": "country",
                            "in": "query",
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                        {
                            "name": "season",
                            "in": "query",
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                        {
                            "name": "studio",
                            "in": "query",
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                        {
                            "name": "network",
                            "in": "query",
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Daftar series",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "page": {"type": "integer"},
                                            "items": {
                                                "type": "array",
                                                "items": CARD,
                                            },
                                            "pagination": PAGINATION,
                                        },
                                    }
                                }
                            },
                        },
                        "400": _err("Parameter tidak valid"),
                        "502": _err("Upstream gagal"),
                    },
                }
            },
            "/series/filters": {
                "get": {
                    "summary": "Semua opsi filter yang tersedia",
                    "tags": ["oppadrama"],
                    "responses": {"200": {"description": "Opsi filter"}},
                }
            },
            "/series/latest": {
                "get": {
                    "summary": "Rilisan episode terbaru",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}}
                    ],
                    "responses": {"200": {"description": "Episode terbaru"}},
                }
            },
            "/series/list": {
                "get": {
                    "summary": "Daftar A-Z (mode teks)",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}}
                    ],
                    "responses": {"200": {"description": "Daftar A-Z"}},
                }
            },
            "/series/{slug}": {
                "get": {
                    "summary": "Detail series lengkap",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "example": "100-days-of-deception"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Detail series"},
                        "404": _err("Slug tidak ditemukan"),
                        "502": _err("Upstream gagal"),
                    },
                }
            },
            "/series/{slug}/episodes": {
                "get": {
                    "summary": "Daftar episode satu series",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Daftar episode",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "total": {"type": "integer"},
                                            "episodes": {
                                                "type": "array",
                                                "items": EPISODE,
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/episode/{slug}": {
                "get": {
                    "summary": "Detail episode + seluruh server mirror",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": "string",
                                "example": "100-days-of-deception-episode-4",
                            },
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Detail episode",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "mirrors": {
                                                "type": "array",
                                                "items": MIRROR,
                                            }
                                        },
                                    }
                                }
                            },
                        },
                        "404": _err("Episode tidak ditemukan"),
                    },
                }
            },
            "/episode/{slug}/stream": {
                "get": {
                    "summary": "Stream HLS siap putar (resolusi server default)",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "server",
                            "in": "query",
                            "description": "Index server (mulai 1). Default server pertama.",
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Info stream + kualitas + proxyUrl",
                            "content": {"application/json": {"schema": STREAM}},
                        }
                    },
                }
            },
            "/stream": {
                "get": {
                    "summary": "Resolusi embed vidara -> info stream HLS",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "url",
                            "in": "query",
                            "required": True,
                            "description": "URL embed (https://vidara.to/e/<filecode>) atau filecode",
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Info stream",
                            "content": {"application/json": {"schema": STREAM}},
                        },
                        "400": _err("Parameter tidak valid"),
                        "502": _err("Upstream gagal"),
                    },
                }
            },
            "/stream/playlist": {
                "get": {
                    "summary": "Proxy playlist HLS (semua URI diarahkan ulang ke API)",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "u",
                            "in": "query",
                            "required": True,
                            "description": "URL master/varian m3u8",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "r",
                            "in": "query",
                            "description": "Referer upstream (opsional)",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "raw",
                            "in": "query",
                            "description": "raw=1 untuk playlist tanpa rewrite",
                            "schema": {"type": "string", "enum": ["1"]},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Playlist m3u8",
                            "content": {
                                "application/vnd.apple.mpegurl": {
                                    "schema": {"type": "string"}
                                }
                            },
                        }
                    },
                }
            },
            "/stream/seg": {
                "get": {
                    "summary": "Relay byte segmen/subtitle (Range diteruskan)",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "u",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "r",
                            "in": "query",
                            "description": "Referer upstream (opsional)",
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Byte segmen",
                            "content": {
                                "application/octet-stream": {
                                    "schema": {"type": "string", "format": "binary"}
                                }
                            },
                        }
                    },
                }
            },
            "/search": {
                "get": {
                    "summary": "Cari drama / series / film",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string", "example": "deception"},
                        },
                        {
                            "name": "page",
                            "in": "query",
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Hasil pencarian",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string"},
                                            "count": {"type": "integer"},
                                            "items": {"type": "array", "items": CARD},
                                        },
                                    }
                                }
                            },
                        },
                        "400": _err("Parameter tidak valid"),
                    },
                }
            },
            "/genres": {
                "get": {
                    "summary": "Semua genre + jumlah judul",
                    "tags": ["oppadrama"],
                    "responses": {"200": {"description": "Daftar genre"}},
                }
            },
            "/genre/{slug}": {
                "get": {
                    "summary": "Series per genre",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "example": "romance"},
                        },
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip genre"}},
                }
            },
            "/country/{slug}": {
                "get": {
                    "summary": "Series per negara",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "example": "south-korea"},
                        },
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip negara"}},
                }
            },
            "/cast/{slug}": {
                "get": {
                    "summary": "Series per pemain",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip pemain"}},
                }
            },
            "/director/{slug}": {
                "get": {
                    "summary": "Series per sutradara",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip sutradara"}},
                }
            },
            "/tag/{slug}": {
                "get": {
                    "summary": "Series per tag",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip tag"}},
                }
            },
            "/network/{slug}": {
                "get": {
                    "summary": "Series per jaringan TV",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip network"}},
                }
            },
            "/season/{slug}": {
                "get": {
                    "summary": "Series per musim",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip musim"}},
                }
            },
            "/studio/{slug}": {
                "get": {
                    "summary": "Series per studio",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "Arsip studio"}},
                }
            },
            "/home/{section}": {
                "get": {
                    "summary": "Satu bagian beranda (ongoing/recommendation/newseries)",
                    "tags": ["oppadrama"],
                    "parameters": [
                        {
                            "name": "section",
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": "string",
                                "enum": ["ongoing", "recommendation", "newseries"],
                            },
                        }
                    ],
                    "responses": {"200": {"description": "Bagian beranda"}},
                }
            },
            "/domains": {
                "get": {
                    "summary": "Info domain aktif & kandidat cadangan",
                    "tags": ["oppadrama"],
                    "responses": {"200": {"description": "Info domain"}},
                }
            },
            "/health": {
                "get": {
                    "summary": "Status layanan & cache",
                    "tags": ["oppadrama"],
                    "responses": {"200": {"description": "Status"}},
                }
            },
        },
        "components": {
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "message": {"type": "string"},
                        "error": {"type": "string"},
                        "hint": {"type": "string"},
                    },
                }
            }
        },
    }
