"""Tes endpoint HTTP tanpa jaringan (mock upstream)."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oppadrama_api import http  # noqa: E402
from oppadrama_api.app import app  # noqa: E402

DETAIL_HTML = """
<html><body>
<div class="bigcontent"><div class="infox">
  <h1 class="entry-title">Demo Show</h1>
  <span class="alter">Alias Show</span>
  <div class="spe">
    <span><b>Status:</b> Ongoing</span>
    <span><b>Negara:</b> <a href="https://oppadrama.io/country/south-korea/" rel="tag">South Korea</a></span>
    <span><b>Tipe:</b> Drama</span>
    <span><b>Episode:</b> 12</span>
  </div>
  <div class="genxed"><a href="https://oppadrama.io/genres/romance/" rel="tag">Romance</a></div>
  <div class="desc">Deskripsi demo.</div>
</div></div>
<div class="eplister"><ul>
  <li><a href="https://oppadrama.io/demo-show-episode-1/">
    <div class="epl-num">1</div><div class="epl-title">Demo Show Episode 1</div>
    <div class="epl-date">October 1, 2026</div></a></li>
</ul></div>
</body></html>
"""

EPISODE_HTML = """
<html><body>
<h1 class="entry-title">Demo Show Episode 1</h1>
<div class="megavid">
  <div class="tb"><img src="https://oppadrama.io/p.jpg" /></div>
  <span class="epx">Drama <span class="lg">Sub</span></span>
  <span class="year">Series <a href="https://oppadrama.io/series/demo-show/">Demo Show</a></span>
  <div class="video-content"><div class="player-embed">
    <iframe src="https://vidara.to/e/DEMO123"></iframe>
  </div></div>
</div>
<select class="mirror" name="mirror">
  <option value="">Pilih Server Video</option>
  <option value="PGlmcmFtZSBzcmM9Imh0dHBzOi8vdmlkYXJhLnRvL2UvREVNTzEyMyI+PC9pZnJhbWU+" data-index="1">vidara</option>
</select>
<div class="dlbox"><ul>
  <li><span class="q"><b>Server A</b></span><span class="w">1080p</span>
      <span class="e"><a href="https://example.com/dl">Download</a></span></li>
</ul></div>
</body></html>
"""

CARDS_HTML = """
<div class="listupd"><article class="bs"><div class="bsx">
  <a href="https://oppadrama.io/series/demo-show/" title="Demo Show" class="tip" rel="1">
  <div class="limit"><div class="typez Drama">Drama</div>
  <div class="bt"><span class="epx">Ongoing</span></div>
  <img src="https://oppadrama.io/p.jpg"/></div></a></div></article></div>
"""


def _fake_get_text(url, **kwargs):
    if "demo-show-episode-1" in url and "/series/" not in url:
        return EPISODE_HTML
    if "/series/demo-show" in url:
        return DETAIL_HTML
    if "search" in url or "?s=" in url:
        return CARDS_HTML
    return CARDS_HTML


class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        http.clear_cache()

    def test_index_and_health(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["success"])

        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"]["status"], "ok")

    def test_openapi_and_docs(self):
        r = self.client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        spec = r.get_json()
        self.assertEqual(spec["info"]["title"], "oppadrama-api")
        self.assertIn("/episode/{slug}/stream", spec["paths"])

        for path in ("/docs", "/player"):
            with self.client.get(path) as resp:
                self.assertEqual(resp.status_code, 200)

    @mock.patch("oppadrama_api.scraper.get_text", side_effect=_fake_get_text)
    def test_series_detail(self, _):
        r = self.client.get("/series/demo-show")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()["data"]
        self.assertEqual(data["title"], "Demo Show")
        self.assertEqual(data["meta"]["totalEpisodes"], 12)
        self.assertEqual(len(data["episodes"]), 1)

    @mock.patch("oppadrama_api.scraper.get_text", side_effect=_fake_get_text)
    def test_episode_detail(self, _):
        r = self.client.get("/episode/demo-show-episode-1")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()["data"]
        self.assertEqual(len(data["mirrors"]), 1)
        self.assertEqual(data["downloads"][0]["quality"], "1080p")
        self.assertTrue(data["streamEndpoint"].endswith("/stream"))

    @mock.patch("oppadrama_api.scraper.get_text", side_effect=_fake_get_text)
    def test_search(self, _):
        r = self.client.get("/search?q=demo")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.get_json()["data"]["count"], 1)

    def test_validation_errors(self):
        self.assertEqual(self.client.get("/search").status_code, 400)
        self.assertEqual(self.client.get("/series?status=bogus").status_code, 400)
        self.assertEqual(self.client.get("/series?page=0").status_code, 400)
        self.assertEqual(self.client.get("/stream").status_code, 400)
        self.assertEqual(self.client.get("/home/nosuchsection").status_code, 400)
        self.assertEqual(self.client.get("/nope").status_code, 404)

    def test_stream_missing_embed(self):
        r = self.client.get("/stream?url=not-a-valid-embed")
        self.assertEqual(r.status_code, 400)


class TestStreamHelpers(unittest.TestCase):
    def test_extract_filecode(self):
        from oppadrama_api import stream

        self.assertEqual(
            stream.extract_filecode("https://vidara.to/e/ABC123"), "ABC123"
        )
        self.assertEqual(stream.extract_filecode("ABC123"), "ABC123")
        self.assertIsNone(stream.extract_filecode("https://vidara.to/"))

    def test_parse_master(self):
        from oppadrama_api import stream

        master = (
            "#EXTM3U\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=910000,RESOLUTION=854x480\n"
            "index_854x480.m3u8?token=x\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=2600000,RESOLUTION=1920x1080\n"
            "index_1920x1080.m3u8?token=x\n"
        )
        q = stream.parse_master("https://cdn/hls/id/master.m3u8", master)
        self.assertEqual(len(q), 2)
        self.assertEqual(q[0]["label"], "480p")
        self.assertTrue(q[0]["url"].startswith("https://cdn/hls/id/"))

    def test_guess_segment_type(self):
        from oppadrama_api import stream

        # Upstream menyamarkan .js sebagai application/javascript.
        self.assertEqual(
            stream.guess_segment_type(
                "https://cdn/hls/id/seg_000.js", "application/javascript"
            ),
            "video/mp2t",
        )
        self.assertEqual(
            stream.guess_segment_type("https://cdn/hls/id/seg_000.ts", None),
            "video/mp2t",
        )
        self.assertEqual(
            stream.guess_segment_type("https://cdn/x/sub.vtt", "text/vtt"),
            "text/vtt",
        )

    def test_rewrite_m3u8(self):
        from oppadrama_api import stream

        text = (
            "#EXTM3U\n"
            "#EXT-X-KEY:METHOD=AES-128,URI=\"key.bin\"\n"
            "#EXTINF:10,\nseg_000.ts\n"
        )
        out = stream.rewrite_m3u8(
            "https://cdn/hls/id/index.m3u8", text, proxy_base=""
        )
        self.assertIn("/stream/seg?u=", out)
        self.assertIn("URI=\"/stream/seg?u=", out)
        self.assertNotIn("\nseg_000.ts", out)


if __name__ == "__main__":
    unittest.main()
