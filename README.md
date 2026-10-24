# oppadrama-api

REST API scraper untuk **[OPPADRAMA](https://oppadrama.io/)** — drama Korea/China/Thailand/Jepang,
series, anime, variety show, dan film **subtitle Indonesia**.

Menyediakan metadata lengkap (judul alternatif, sinopsis, cast, sutradara, genre,
rating, status, negara, jaringan TV), daftar episode, **server streaming HLS**
(1080p / 720p / 480p) yang **siap diputar** di hls.js / Video.js, link download,
pencarian, dan seluruh arsip taksonomi.

```bash
pip install -r requirements.txt
python -m oppadrama_api.app
# -> http://127.0.0.1:5000/docs
```

> ⚠️ **Proyek edukasi.** API ini tidak menghosting konten apa pun. Semua data
> dibaca dari halaman publik oppadrama.io dan tautan streaming dimiliki pihak
> ketiga. Gunakan dengan bijak dan hormati situs sumber.

---

## Daftar endpoint

| Method | Path | Isi |
|---|---|---|
| GET | `/` | Daftar endpoint |
| GET | `/health` | Status layanan & cache |
| GET | `/docs` | Dokumentasi Swagger UI |
| GET | `/player` | Halaman uji pemutaran HLS di browser |
| GET | `/openapi.json` | Skema OpenAPI 3.0 |
| GET | `/home?page=1` | Beranda: rilis terbaru, rekomendasi, sidebar |
| GET | `/home/{section}` | Satu bagian beranda (`ongoing`, `recommendation`, `newseries`, `latest`) |
| GET | `/series` | Daftar series + filter (status, tipe, genre, negara, musim, studio, network, urutan) |
| GET | `/series/filters` | Semua opsi filter yang tersedia |
| GET | `/series/latest?page=1` | Rilisan episode terbaru |
| GET | `/series/list?page=1` | Daftar A–Z (mode teks) |
| GET | `/series/{slug}` | Detail series lengkap |
| GET | `/series/{slug}/episodes` | Daftar episode satu series |
| GET | `/episode/{slug}` | Detail episode + seluruh server mirror + link download |
| GET | `/episode/{slug}/stream` | **Stream HLS siap putar** untuk server terpilih |
| GET | `/stream?url=` | Resolusi embed vidara → info stream |
| GET | `/stream/playlist?u=` | Proxy playlist HLS (semua URI diarahkan ulang) |
| GET | `/stream/seg?u=` | Relay byte segmen/subtitle (Range diteruskan) |
| GET | `/search?q=` | Cari drama / series / film |
| GET | `/genres` | Semua genre + jumlah judul |
| GET | `/genre/{slug}` | Series per genre |
| GET | `/country/{slug}` | Series per negara |
| GET | `/cast/{slug}` | Series per pemain |
| GET | `/director/{slug}` | Series per sutradara |
| GET | `/tag/{slug}` | Series per tag |
| GET | `/network/{slug}` | Series per jaringan TV |
| GET | `/season/{slug}` | Series per musim |
| GET | `/studio/{slug}` | Series per studio |
| GET | `/domains` | Info domain aktif & kandidat cadangan |

Section beranda: `ongoing` (Sedang Tayang), `recommendation` (Rekomendasi per genre),
`newseries` (Judul Drama/Series Baru), `latest` (Rilisan Terbaru).

---

## Contoh

### Beranda

```bash
curl 'http://127.0.0.1:5000/home'
curl 'http://127.0.0.1:5000/home/ongoing'
```

### Cari & detail

```bash
curl 'http://127.0.0.1:5000/search?q=deception'
curl 'http://127.0.0.1:5000/series/100-days-of-deception'
curl 'http://127.0.0.1:5000/series/100-days-of-deception/episodes'
curl 'http://127.0.0.1:5000/episode/100-days-of-deception-episode-4'
```

### Filter katalog

```bash
# Drama Korea yang sedang tayang, urut terbaru
curl 'http://127.0.0.1:5000/series?country=south-korea&status=ongoing&order=update'

# Beberapa genre sekaligus
curl 'http://127.0.0.1:5000/series?genre=action&genre=romance&type=drama'
```

### Memutar streaming

Satu langkah — ambil stream siap pakai:

```bash
curl 'http://127.0.0.1:5000/episode/100-days-of-deception-episode-4/stream'
```

Respons memuat `data.masterProxyUrl` (playlist master lewat proxy API) dan
`data.qualities[]` dengan `proxyUrl` per kualitas. Tunjuk `masterProxyUrl` atau
`proxyUrl` mana pun langsung ke `hls.js`:

```html
<script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
<video id="v" controls></video>
<script>
  const src = "http://127.0.0.1:5000" + data.masterProxyUrl; // dari response API
  const video = document.getElementById("v");
  if (Hls.isSupported()) {
    const hls = new Hls();
    hls.loadSource(src);
    hls.attachMedia(video);
  } else {
    video.src = src; // Safari/iOS native HLS
  }
</script>
```

Pilih server lain bila ada beberapa mirror:

```bash
curl 'http://127.0.0.1:5000/episode/100-days-of-deception-episode-4/stream?server=2'
```

Atau resolusi manual dari URL embed:

```bash
curl 'http://127.0.0.1:5000/stream?url=https://vidara.to/e/2gxTamNdmrlOo'
```

### Uji langsung di browser

Buka `http://127.0.0.1:5000/player`, masukkan slug episode, klik **Muat Stream**.
Halaman itu memakai hls.js dan memutar lewat endpoint proxy API yang sama —
cara tercepat memastikan hasil scraping benar-benar bisa diputar.

**Kenapa perlu proxy?** Playlist HLS dari CDN penyedia membawa token yang terikat
ke alamat IP pemanggil dan bisa menolak permintaan lintas-origin. Endpoint
`/stream/playlist` dan `/stream/seg` meneruskan permintaan dengan `Referer` yang
benar, menulis ulang setiap URI di playlist agar menunjuk kembali ke API, dan
meneruskan header `Range`, sehingga hasilnya dapat diputar dari mana saja.

---

## Format respons

Semua endpoint mengembalikan JSON dengan pembungkus konsisten:

```json
{ "success": true, "data": { "...": "..." } }
```

Error:

```json
{ "success": false, "message": "Series tidak ditemukan", "hint": "..." }
```

Kode status: `400` parameter tidak valid, `404` slug tidak ada, `502` upstream gagal.

### Ringkasan bentuk `data`

**Kartu** (`/home`, `/series`, `/search`, arsip):

```json
{
  "title": "100 Days of Deception",
  "slug": "100-days-of-deception",
  "url": "https://oppadrama.io/series/100-days-of-deception/",
  "type": "Drama",
  "poster": "https://i2.wp.com/...jpg",
  "episode": null,
  "episodeLabel": "Ongoing",
  "sub": "Sub",
  "status": "Ongoing",
  "updatedAgo": "6 hours lalu",
  "movieId": "6835"
}
```

**Detail series** (`/series/{slug}`) menambahkan `altTitle`, `synopsis`,
`description`, `genres`, `tags`, `rating {value,count}`, `meta` (status, network,
country, director, cast, totalEpisodes, duration, released, updated), dan
`episodes[]`.

**Detail episode** (`/episode/{slug}`):

```json
{
  "title": "100 Days of Deception Episode 4",
  "type": "Drama",
  "series": { "title": "100 Days of Deception", "slug": "100-days-of-deception" },
  "mirrors": [
    { "name": "vidara.to", "host": "vidara.to",
      "embed": "https://vidara.to/e/2gxTamNdmrlOo", "index": 1 }
  ],
  "downloads": [
    { "server": "Buzzheavier", "quality": "FHD 1080p",
      "url": "https://buzzheavier.com/gqo6ykb3oo3x" }
  ],
  "prev": "https://oppadrama.io/...episode-3/",
  "next": null
}
```

**Stream** (`/episode/{slug}/stream`, `/stream`):

```json
{
  "filecode": "2gxTamNdmrlOo",
  "streamingUrl": "https://s13-....com/hls/.../master.m3u8?token=...",
  "isMaster": true,
  "qualityLabels": ["1080p", "720p", "480p"],
  "masterProxyUrl": "/api/oppadrama-api/stream/playlist?u=...",
  "qualities": [
    { "label": "1080p", "resolution": "1920x1080", "bandwidth": 2600000,
      "url": "https://s13-.../index_1920x1080.m3u8?token=...",
      "proxyUrl": "/api/oppadrama-api/stream/playlist?u=..." }
  ],
  "subtitles": [],
  "thumbnail": "https://...jpg"
}
```

---

## Konfigurasi

Lewat environment variable:

| Variabel | Default | Keterangan |
|---|---|---|
| `PORT` | `5000` | Port server |
| `OPPADRAMA_BASE_URL` | `https://oppadrama.io` | Domain upstream |
| `OPPADRAMA_DOMAINS` | `https://oppadrama.io` | Daftar kandidat domain (dipisah koma) |
| `OPPADRAMA_TIMEOUT` | `25` | Timeout HTTP (detik) |
| `OPPADRAMA_CACHE_TTL` | `300` | TTL cache halaman HTML (detik) |
| `OPPADRAMA_STREAM_CACHE_TTL` | `600` | TTL cache hasil resolusi stream (detik) |
| `OPPADRAMA_MAX_RETRIES` | `3` | Jumlah percobaan ulang |
| `OPPADRAMA_MAX_PAGE` | `500` | Batas nomor halaman |

Cache disimpan di memori (tanpa database) dan dibersihkan otomatis saat entri
kedaluwarsa.

---

## Deployment

### Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 'oppadrama_api.app:app'
```

### Docker

```bash
docker build -t oppadrama-api .
docker run -d --name oppadrama-api -p 5000:5000 oppadrama-api
```

### Di belakang gateway (path prefix)

Aplikasi sadar akan `SCRIPT_ROOT`, jadi bila dipasang di sub-path seperti
`/api/oppadrama-api`, seluruh URL di dokumentasi dan proxy playlist otomatis
mengikuti prefix tersebut. Contoh Nginx:

```nginx
location /api/oppadrama-api/ {
    proxy_pass http://127.0.0.1:5001/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Prefix /api/oppadrama-api;
}
```

---

## Catatan teknis

- **Sumber:** situs berjalan di WordPress dengan tema Themesia. Struktur yang
  dipakai: `article.bs` (kartu), `.bigcontent .infox` (detail series),
  `.megavid` + `select.mirror` (episode), `.eplister` (daftar episode).
- **Player:** setiap episode menyematkan iframe dari `vidara.to`. Filecode pada
  URL embed dikirim ke `POST https://vidara.to/api/stream` untuk memperoleh
  master HLS bertoken. Resolver menangani host mirror dan fallback otomatis.
- **Subtitle** diambil dari field `subtitles` upstream bila tersedia; saat ini
  umumnya kosong.
- Tanpa database, tanpa state — cukup Python 3.9+.

## Lisensi

MIT. Proyek edukasi, tidak berafiliasi dengan oppadrama.io.
