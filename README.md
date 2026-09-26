# Market Intelligence & Prospect Identification System

Implementasi sistem sesuai Use Case Diagram (7 modul):
1. Data Collection (Upload File, Scraping URL, Integrasi API, Input Manual)
2. Data Processing & AI (Klasifikasi, Mapping Kolom, Validasi, Deduplication, Enrichment — via Groq AI Agent)
3. Prospect Management (List, Filter/Search, Segmentasi, Scoring, CRUD)
4. Market Analysis (Tren Pasar, Distribusi Industri/Wilayah/Ukuran, Rekomendasi Produk AI)
5. Marketing Delivery (Dataset Campaign, Export Lead List, Kelola Segmentasi Campaign)
6. Reporting (Laporan Market Intelligence AI, Dashboard, Export Laporan)
7. System Management (User & Hak Akses, Sumber Data, Monitoring, Cron Job, Log Aktivitas, Konfigurasi AI Agent)

Tech stack: **Flask** (app factory + blueprint per modul), **MySQL** (via SQLAlchemy + PyMySQL),
**Groq** sebagai AI Agent (`app/ai_agent.py`), Bootstrap 5 + Chart.js untuk UI.

## 1. Setup Database MySQL

```sql
-- opsional, database & tabel juga otomatis dibuat oleh SQLAlchemy saat app pertama kali jalan
CREATE DATABASE market_intelligence CHARACTER SET utf8mb4;
```

Atau jalankan file `schema.sql` langsung di MySQL jika ingin membuat tabel secara manual:
```bash
mysql -u root -p < schema.sql
```

## 2. Setup environment

```bash
cd market_intelligence
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`, isi kredensial MySQL dan `GROQ_API_KEY` (dapatkan dari https://console.groq.com/keys).

## 3. Jalankan aplikasi

```bash
python run.py
```

Buka `http://localhost:5000`. Karena belum ada user, buka `http://localhost:5000/register`
untuk membuat akun **admin** pertama kali. Setelah itu registrasi mandiri otomatis nonaktif
(user baru dibuat lewat menu Admin > Kelola Pengguna).

## 4. Struktur Proyek

```
market_intelligence/
├── run.py
├── requirements.txt
├── schema.sql
├── .env.example
├── app/
│   ├── __init__.py        # App factory, registrasi blueprint
│   ├── config.py          # Konfigurasi (MySQL, Groq, upload)
│   ├── extensions.py      # db, login_manager
│   ├── models.py          # Semua tabel (User, Prospect, RawData, dst)
│   ├── ai_agent.py         # Semua fungsi AI Agent (Groq)
│   ├── utils.py            # log_activity, roles_required, allowed_file
│   ├── blueprints/
│   │   ├── auth/                → login/register
│   │   ├── data_collection/     → modul 1
│   │   ├── data_processing/     → modul 2 (AI)
│   │   ├── prospect/            → modul 3
│   │   ├── market_analysis/     → modul 4 (AI)
│   │   ├── marketing/           → modul 5
│   │   ├── reporting/           → modul 6 (AI)
│   │   └── admin/               → modul 7
│   ├── templates/          # Jinja2 + Bootstrap 5
│   └── static/
```

## 5. Catatan AI Agent (Groq)

Semua use case AI pada diagram diimplementasikan di `app/ai_agent.py`, dipanggil dari blueprint terkait:

| Use Case (diagram)                  | Fungsi di `ai_agent.py`     | Dipanggil dari                          |
|--------------------------------------|------------------------------|------------------------------------------|
| Klasifikasi Jenis Data                | `classify_data()`            | `data_processing` → `/classify`          |
| Mapping Kolom                         | `map_columns()`              | `data_processing` → `/map-columns`       |
| Validasi & Deteksi Data Tidak Valid   | `validate_record()`          | `data_processing` → `/process`           |
| Enrichment Data                       | `enrich_prospect()`          | `data_processing` → `/process` (opsional)|
| Menentukan Prioritas Prospek (Scoring)| `score_prospect()`           | `prospect` → `/score`, `/segment-all`    |
| Rekomendasi Potensi Produk            | `recommend_products()`       | `market_analysis` → `/product-recommendation` |
| Ringkasan Laporan Market Intelligence | `summarize_report()`         | `reporting` → `/generate`                |

Model default: `llama-3.3-70b-versatile` (bisa diganti lewat `.env` → `GROQ_MODEL`, atau via
menu Admin > Konfigurasi AI Agent untuk dicatat sebagai referensi).

## 6. Discovery Organisasi dan Event

Menu **Admin > Discovery Organisasi & Event** menyediakan registry sumber yang dinamis.
Admin dapat memasukkan kategori, keyword, wilayah, dan/atau URL sumber resmi. Sistem akan
mencari URL melalui DuckDuckGo HTML Search secara default, atau Bing Web Search API/Google
Custom Search API jika dipilih dan credential-nya tersedia. Setelah itu sistem mengambil
halaman publik, membaca JSON-LD, email, telepon, alamat, website, dan link media sosial.

Hasil disimpan terpisah ke tabel `organizations` dan `events`, dengan deduplikasi berdasarkan
URL sumber dan skor relevansi awal terhadap kebutuhan apparel. Discovery juga bisa dijalankan
otomatis melalui tipe Cron Job `discovery_sync`.

Konfigurasi opsional di `.env`:

```env
SEARCH_PROVIDER=duckduckgo
DUCKDUCKGO_VERIFY_SSL=false
BING_SEARCH_API_KEY=
GOOGLE_SEARCH_API_KEY=
GOOGLE_SEARCH_ENGINE_ID=
```

Sistem tidak menyimpan halaman hasil pencarian sebagai data organisasi/event. Search hanya
dipakai untuk menemukan URL; detail dibaca dari website publik sumbernya. DuckDuckGo dapat
mengalami certificate mismatch pada beberapa jaringan/proxy lokal. `DUCKDUCKGO_VERIFY_SSL=false`
adalah compatibility mode khusus request discovery DuckDuckGo; gunakan `true` pada server
dengan sertifikat jaringan yang normal. DuckDuckGo juga dapat membatasi request otomatis, jadi
gunakan scheduler dengan interval wajar dan tetap pastikan
sumber serta metode pengambilan data mematuhi ketentuan layanan masing-masing penyedia.

## 7. Cron Job / Scheduler

Menu **Admin > Mengatur Jadwal Cron Job** sekarang mendaftarkan job aktif ke
**APScheduler background scheduler** saat aplikasi berjalan. Job yang tersedia:

- `scraping`: mengambil ulang semua sumber URL yang tersimpan sebagai `DataSource`.
- `ai_classification`: mengklasifikasikan `RawData` berstatus `extracted`.
- `enrichment`: melengkapi prospek yang belum memiliki industri atau ukuran perusahaan.
- `report_generation`: membuat laporan Market Intelligence dengan ringkasan AI.
- `discovery_sync`: menjalankan semua Discovery Source aktif untuk organisasi dan event.

Ekspresi cron menggunakan format lima kolom, misalnya `0 6 * * *`. Status `running`,
`success`, atau `error` dan waktu eksekusi terakhir disimpan di `cron_jobs` dan ditampilkan
di **Admin > Monitoring**. Scheduler berjalan di dalam proses Flask, jadi pada deployment
dengan banyak worker sebaiknya hanya jalankan satu worker aplikasi atau pindahkan scheduler
ke proses worker khusus agar job tidak dieksekusi ganda.

## 8. Login default

Belum ada seed user — buat akun admin pertama lewat `/register` setelah database siap.
