"""Tes parser offline memakai HTML contoh (tanpa jaringan)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oppadrama_api import parsers  # noqa: E402

CARD_HTML = """
<div class="listupd">
  <article class="bs">
    <div class="bsx">
      <a href="https://oppadrama.io/series/100-days-of-deception/" title="100 Days of Deception" class="tip" rel="6835">
        <div class="limit">
          <div class="typez Drama">Drama</div>
          <div class="bt"><span class="epx">Ongoing</span><span class="sb Sub">Sub</span></div>
          <img src="https://oppadrama.io/poster.jpg" />
        </div>
        <div class="tt tts">100 Days of Deception<h2 itemprop="headline">100 Days of Deception</h2></div>
      </a>
    </div>
  </article>
  <article class="bs">
    <div class="bsx">
      <a href="https://oppadrama.io/lupin-season-4-episode-8-end/" title="Lupin Season 4 Episode 8 END" class="tip" rel="8335">
        <div class="limit">
          <div class="typez Drama">Drama</div>
          <div class="bt"><span class="epx">Ep 8</span><span class="sb Sub">Sub</span></div>
          <img src="https://oppadrama.io/lupin.jpg" />
        </div>
        <div class="ttt"><div class="tt">Lupin Season 4<h2 itemprop="headline">Lupin Season 4 Episode 8 END</h2></div></div>
      </a>
    </div>
  </article>
</div>
"""

PAGINATION_HTML = """
<div class="pagination">
  <a class="prev page-numbers" href="https://oppadrama.io/genres/romance/">&laquo; Previous</a>
  <a class="page-numbers" href="https://oppadrama.io/genres/romance/">1</a>
  <span aria-current="page" class="page-numbers current">2</span>
  <a class="page-numbers" href="https://oppadrama.io/genres/romance/page/3/">3</a>
  <a class="next page-numbers" href="https://oppadrama.io/genres/romance/page/3/">Next &raquo;</a>
</div>
"""

MIRROR_HTML = """
<select class="mirror" name="mirror">
  <option value="">Pilih Server Video</option>
  <option value="PGlmcmFtZSBzcmM9Imh0dHBzOi8vdmlkYXJhLnRvL2UvMmd4VGFtTmRtcmxPbyI+PC9pZnJhbWU+" data-index="1">vidara</option>
</select>
"""

HOME_MARKER = """
<div class="bixbox"><div class="releases latesthome"><h3>Rilisan Terbaru</h3></div>
<article class="bs"><div class="bsx"><a href="/x/" class="tip"><img src="/a.jpg"/></a></div></article></div>
"""


class TestCards(unittest.TestCase):
    def test_parse_cards(self):
        cards = parsers.parse_cards(CARD_HTML)
        self.assertEqual(len(cards), 2)

        first = cards[0]
        self.assertEqual(first["title"], "100 Days of Deception")
        self.assertEqual(first["slug"], "100-days-of-deception")
        self.assertEqual(first["type"], "Drama")
        self.assertEqual(first["status"], "Ongoing")
        self.assertEqual(first["sub"], "Sub")
        self.assertEqual(first["movieId"], "6835")
        self.assertTrue(first["poster"].startswith("https://"))

        second = cards[1]
        self.assertEqual(second["episode"], 8)
        self.assertEqual(second["slug"], "lupin-season-4-episode-8-end")

    def test_status_completed(self):
        html = CARD_HTML.replace("Lupin Season 4 Episode 8 END", "X Episode 8 END")
        cards = parsers.parse_cards(html)
        self.assertEqual(cards[1]["status"], "Completed")


class TestPagination(unittest.TestCase):
    def test_pagination(self):
        p = parsers.parse_pagination(PAGINATION_HTML)
        self.assertEqual(p["currentPage"], 2)
        self.assertEqual(p["totalPages"], 3)
        self.assertEqual(p["nextPage"], 3)
        self.assertEqual(p["prevPage"], 1)
        self.assertTrue(p["hasNext"])

    def test_empty_pagination(self):
        p = parsers.parse_pagination("<div></div>")
        self.assertFalse(p["hasNext"])
        self.assertEqual(p["currentPage"], 1)


class TestMirrors(unittest.TestCase):
    def test_decode_mirror(self):
        mirrors = parsers.parse_mirrors(MIRROR_HTML)
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(mirrors[0]["embed"], "https://vidara.to/e/2gxTamNdmrlOo")
        self.assertEqual(mirrors[0]["host"], "vidara.to")
        self.assertEqual(mirrors[0]["index"], 1)


class TestHelpers(unittest.TestCase):
    def test_absolute(self):
        self.assertEqual(parsers.absolute("/x/y"), "https://oppadrama.io/x/y")
        self.assertEqual(parsers.absolute("//cdn/x"), "https://cdn/x")
        self.assertIsNone(parsers.absolute("#frag"))
        self.assertEqual(
            parsers.absolute("https://other/x"), "https://other/x"
        )

    def test_slug_from_url(self):
        self.assertEqual(
            parsers.slug_from_url("https://oppadrama.io/series/foo-bar/", "series"),
            "foo-bar",
        )
        self.assertEqual(
            parsers.slug_from_url("https://oppadrama.io/foo-episode-1/", "any"),
            "foo-episode-1",
        )
        self.assertIsNone(parsers.slug_from_url("https://oppadrama.io/", "series"))

    def test_not_found_detection(self):
        self.assertTrue(parsers.is_not_found_page(HOME_MARKER))
        detail = '<div class="bigcontent"><div class="infox"><h1 class="entry-title">X</h1></div></div>'
        self.assertFalse(parsers.is_not_found_page(detail))


if __name__ == "__main__":
    unittest.main()
