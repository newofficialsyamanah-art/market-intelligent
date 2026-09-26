# Buku Panduan Pengguna
## SYAMANAH Indonesia Market & Organization Intelligence

Panduan ini ditujukan untuk pengguna non-teknis dan lintas peran. Gunakan aplikasi untuk menemukan dan mengelola intelijen institusi/organisasi di Indonesia (pendidikan, komunitas, ormawa, asosiasi, perusahaan), mengekstrak sinyal media sosial publik, membaca peluang pasar, menilai kesesuaian produk (AI Product Fit) untuk Jersey/Teamwear, mengelola kampanye marketing terarah, serta menjalankan automasi terjadwal.

---

## 1. Gambaran Singkat & Alur Sistem

Aplikasi beroperasi sebagai sistem **Indonesia Market & Organization Intelligence** terpadu melalui alur:

```
SUMBER PUBLIK / FILE / API / SOCIAL MEDIA
           ↓
DISCOVERY & INGESTION (Pendidikan, Komunitas, Ormawa, Organisasi)
           ↓
PROSPECT LAYER (Compatibility & Ingestion Gateway)
           ↓
IDENTITY RESOLUTION & DEDUPLIKASI (Non-destructive, Provenance)
           ↓
MASTER ORGANIZATIONS (Single Source of Truth)
           ↓
ENRICHMENT & SOCIAL SIGNAL EXTRACTION (Instagram, TikTok, FB, LinkedIn)
           ↓
EVENT & ACTIVITY INTELLIGENCE (Turnamen, Kejuaraan, Dies Natalis)
           ↓
EXPLAINABLE AI PRODUCT FIT (Jersey, Custom Teamwear, Seragam)
           ↓
MARKETING TARGET EXPLORER & CAMPAIGN MANAGEMENT
           ↓
EXECUTIVE REPORTING & EXPORT
```

Semua data yang dihasilkan AI didukung bukti faktual (*verifiable evidence*) dan penjelasan rasional (*reasoning*), serta dapat ditinjau oleh pengguna sebelum dipakai dalam strategi bisnis.

---

## 2. Peran Pengguna (Role-Based Access Control)

Menu dan tampilan dashboard akan menyesuaikan peran akun Anda:

| Peran | Kegunaan Utama & Akses |
|---|---|
| **Admin / IT** | Akses penuh seluruh modul: manajemen user & RBAC, scheduler & automasi cron (10 tugas), pipeline monitoring, trigger discovery, data manager, audit log, dan konfigurasi AI. |
| **Business Analyst** | Mengumpulkan dan memproses data, menjalankan discovery institusi pendidikan dan komunitas, mengelola enrichment sosial, analisis pasar & white-space, kalkulasi AI product fit, dan rekomendasi produk. |
| **Marketing** | Mengeksplorasi target akun dengan filter lengkap (olahraga, subtype, sinyal media sosial, product-fit), mengelola Kampanye Marketing, menambahkan target ber-snapshot intelijen, dan mengunduh lead list. |
| **Management** | Melihat dashboard analitik pasar tingkat tinggi, memantau sebaran industri & wilayah, meninjau kesesuaian produk, melihat metrik kampanye, dan membuat laporan eksekutif. |

---

## 3. Masuk dan Dashboard Berbasis Peran

### 3.1 Masuk (Login)
1. Buka halaman aplikasi.
2. Masukkan email dan password yang terdaftar.
3. Klik **Login**.
4. Pendaftaran akun pertama dilakukan melalui **Register**. Pembuatan dan perubahan akun berikutnya dikelola oleh Admin melalui **Admin Panel > Kelola User & RBAC**.

### 3.2 Dashboard Utama Berbasis Peran
Setelah masuk, sistem secara dinamis menampilkan dashboard yang disesuaikan dengan peran Anda:

- **Dashboard Admin**:
  - Menampilkan status scheduler & cron (`Aktif / Nonaktif`), antrean data mentah (`Raw Data Queue`), metrik kegagalan job, dan pintasan pemicu discovery otomatis.
  - Kartu ringkasan: Total Organisasi Master, Total Prospek, dan Total Kampanye.
- **Dashboard Business Analyst**:
  - Menampilkan sebaran Universe Discovery (Pendidikan, Komunitas Olahraga, Ormawa, Perusahaan), antrean klasifikasi AI, serta metrik kualitas dan kesegaran data (*data freshness*).
  - Pintasan ke Data Discovery, Pipeline Processing, dan Market Analytics.
- **Dashboard Marketing**:
  - Menampilkan metrik akun berpeluang tinggi (*High Opportunity*), akun *Apparel/Jersey-Fit*, ketersediaan kontak (*Contactability Rate*), serta ringkasan kampanye aktif.
  - Pintasan langsung ke Target Explorer dan Pembuatan Kampanye Baru.
- **Dashboard Management**:
  - Menampilkan gambaran umum kesehatan pasar (*Market Health Index*), rata-rata Opportunity Score, sebaran prioritas Tier A/B/C/D, serta ringkasan kampanye.
  - Akses cepat ke Market Analytics dan Pembuatan Laporan Eksekutif.

---

## 4. Mengumpulkan Data (Data Collection & Ingestion)

Menu: **Company Intelligence > Ingestion Sources** atau **Data Collection**.  
Akses: **Admin** dan **Business Analyst**.

### 4.1 Upload Excel, CSV, atau PDF
Format didukung: `.xlsx`, `.xls`, `.csv`, dan `.pdf`.
1. Pilih **Upload File**.
2. Pilih file dari komputer lokal Anda.
3. Klik **Upload & Ekstrak**.
4. Buka **Detail** pada riwayat data untuk melihat hasil ekstraksi dan pemetaan.

### 4.2 Mengambil Data dari Website Publik (Web Ingestion)
1. Masukkan URL publik resmi (wajib menyertakan `http://` atau `https://`).
2. Klik **Ambil Data dari Website**.
3. Buka **Processing & AI** untuk memeriksa teks dan metadata yang berhasil diekstrak.

### 4.3 Mengambil Data dari API
1. Masukkan **API URL**.
2. Pilih metode **GET** atau **POST**.
3. Isi **Headers JSON** (misalnya token otorisasi) dan **Body JSON** bila diperlukan.
4. Klik **Ambil Data dari API**.

### 4.4 Input Manual
Gunakan form manual untuk menambahkan organisasi/institusi secara cepat dengan mengisi nama, tipe organisasi, subtipus, cabang olahraga (bila relevan), kontak, dan wilayah.

---

## 5. Processing & AI Gateway

Menu: **Company Intelligence > Processing & AI**.  
Akses: **Admin** dan **Business Analyst**.

1. **Klasifikasi AI**: Mengenali format dan kategori entitas yang masuk.
2. **Mapping Kolom (Otomatis / Manual)**: Memetakan kolom file sumber ke skema standar sistem (nama organisasi, tipe, industri, kontak, provinsi, kota, website, medsos).
3. **Proses ke Database**: Menyimpan data yang sudah divalidasi ke layer prospek dan langsung menyelesaikan identitasnya ke Master Organizations.

---

## 6. Prospect Management (Compatibility Layer)

Menu: **Prospects**.  
Akses: Melihat (**Semua Role**), Mengubah/Hapus/Scoring (**Admin** & **Business Analyst**).

Layer Prospek dipertahankan sebagai jembatan kompatibilitas terhadap alur kerja lama:
- Memfilter prospek berdasarkan industri, wilayah, segmen, dan status (`New`, `Qualified`, `Contacted`, `Converted`, `Rejected`).
- Fitur **Scoring & Segmentasi AI** tetap berjalan untuk menghitung prioritas prospek sebelum dikonsolidasikan ke Master Organizations.

---

## 7. Master Organizations & AI Product Fit

Menu: **Company Intelligence > Master Organizations**.  
Akses: **Semua Role** (Melihat & Detail).

`organizations` adalah **Single Source of Truth** untuk seluruh intelijen entitas di Indonesia.

### 7.1 Taksonomi Organisasi & Subtipe
Sistem mencatat klasifikasi yang detail:
- **Tipe Organisasi**: Pendidikan, Komunitas, Ormawa, Perusahaan, Asosiasi, Yayasan, NGO, Ormas, Event Organizer, Pemerintahan.
- **Subtipe Organisasi**:
  - *Pendidikan*: PAUD, TK, SD, MI, SMP, MTs, SMA, MA, SMK, Pesantren, Universitas, Institut, Politeknik, Sekolah Tinggi, Akademi, Fakultas.
  - *Komunitas*: Klub Olahraga, Komunitas Lari/Cycling/Esports, Komunitas Seni/Musik, Hobi, Komunitas Profesi.
  - *Ormawa*: BEM, DPM, HIMA, UKM Kampus.
- **Cabang Olahraga (Sport Tag)**: Futsal, Sepak Bola, Bola Basket, Bola Voli, Lari, Bersepeda, Bulu Tangkis, Esports, dsb.

### 7.2 Profil & Sinyal Media Sosial (Social Signal Extraction)
Setiap organisasi dapat memiliki tautan dan sinyal media sosial publik dari **Instagram**, **TikTok**, **Facebook**, dan **LinkedIn**.
Sinyal yang diekstrak meliputi:
- **Product Signals**: Kata kunci kebutuhan seragam, apparel, jersey tim, jersey printing, merchandise, custom kit.
- **Sport Signals**: Aktivitas pertandingan, sparring, latihan mingguan, liga olahraga.
- **Activity Signals**: Turnamen tahunan, kejuaraan, dies natalis, recruitment anggota, gathering akbar, class meeting.

### 7.3 Explainable AI Product Fit (Jersey & Custom Teamwear)
Setiap organisasi dievaluasi kesesuaian produknya secara objektif dan transparan:
- **Product Fit Score**: Skor 0 – 100 yang merefleksikan probabilitas kebutuhan jersey atau seragam tim.
- **Product Fit Label**:
  - `High Fit` (Skor >= 75): Sangat relevan (misal: UKM Futsal, klub basket, sekolah dengan tim olahraga aktif).
  - `Medium Fit` (Skor 50 – 74): Relevan untuk acara periodik, gathering, atau seragam angkatan.
  - `Low Fit` (Skor 25 – 49): Relevansi terbatas pada seragam formal atau event kasual.
  - `Unlikely Fit` (Skor < 25): Entitas non-aktif atau tidak memiliki aktivitas tim/olahraga.
- **Reasoning**: Narasi logis mengapa organisasi tersebut cocok atau kurang cocok.
- **Verifiable Evidence**: Bukti nyata yang dipakai (subtipe entitas, data olahraga, riwayat partisipasi event turnamen, sinyal medsos). **AI dilarang mengarang bukti**. Jika data minim, status akan ditandai `REVIEW` dengan tingkat keyakinan rendah.

---

## 8. Event & Activity Intelligence

Menu: **Event Intelligence**.  
Akses: Melihat (**Semua Role**), Menambah/Menghubungkan Peserta (**Admin, BA, Marketing**).

Event dan aktivitas merupakan indikator utama momentum pengadaan jersey:
1. **Event Directory & Calendar**: Menampilkan turnamen olahraga, kompetisi antar-sekolah, liga mahasiswa, dan seminar/pameran.
2. **Koneksi Peserta (Participants)**: Menghubungkan Master Organization sebagai *organizer*, *exhibitor*, *sponsor*, *partner*, atau *speaker*.
3. **Korelasi ke Product Fit**: Organisasi yang terdaftar dalam turnamen olahraga secara otomatis memperoleh sinyal aktivitas yang memperkuat skor kesesuaian produk.

---

## 9. Marketing Intelligence & Campaign Management

Menu: **Marketing Intelligence**.  
Akses: **Admin**, **Marketing**, **Business Analyst**, **Management**.

### 9.1 Target Explorer Terintegrasi
Gunakan Target Explorer untuk menemukan target prospek jersey/teamwear terbaik dengan filter:
- **Pencarian Nama & Kata Kunci**.
- **Tipe & Subtipe Organisasi** (misal: hanya SMK, UKM, atau Klub Olahraga).
- **Cabang Olahraga** (misal: Futsal, Running, Basketball).
- **Product-Fit & Minimum Score** (misal: High Fit, skor >= 80).
- **Keberadaan Media Sosial** (Memiliki Instagram, TikTok, Facebook, atau LinkedIn).
- **Kelengkapan Kontak** (Memiliki Email, Telepon, atau Website).
- **Keterlibatan Event** (Hanya organisasi yang aktif mengikuti turnamen/event).
- **Lokasi Geografis** (Provinsi & Kota).

Dari Target Explorer, Anda dapat langsung menambahkan organisasi terpilih ke dalam Kampanye Marketing yang aktif!

### 9.2 Campaign Management (Pencatatan & Pengelolaan Kampanye)
Menu: **Marketing Intelligence > Campaign Management** (atau URL `/marketing/campaigns`).

Fitur ini didesain murni untuk intelijen pemasaran terarah (bukan CRM sales pipeline):
1. **Membuat Kampanye Baru**:
   - Isi Nama Kampanye (misal: *"Promo Jersey Turnamen Futsal Jabar 2026"*).
   - Tentukan Produk Target (default: `Jersey / Custom Teamwear`, Merchandise, Seragam).
   - Tentukan parameter target: Tipe Organisasi, Segmen, Provinsi, Kota, Kanal Outreach (WhatsApp, Email, Instagram DM, Phone).
2. **Menambahkan Target Organisasi**:
   - Dari tabel Target Explorer, pilih target lalu klik **"Tambahkan ke Kampanye"**.
   - Atau dari halaman Detail Organisasi, gunakan tombol **"Assign ke Kampanye"**.
3. **Snapshot Intelijen Otomatis**:
   - Saat organisasi ditambahkan ke kampanye, sistem membekukan snapshot nilai: `product_fit_snapshot` dan `opportunity_score_snapshot`.
   - Ini memastikan performa kampanye dapat diukur secara akurat berdasarkan kondisi intelijen saat target dipilih.
4. **Pelacakan Status Target**:
   - Perbarui status kontak target: `assigned` → `contacted` → `converted` atau `declined`.
   - Tambahkan catatan progres penawaran pada setiap target.
5. **Ekspor Lead List Kampanye**:
   - Klik **"Export Lead List (CSV)"** di halaman detail kampanye untuk mengunduh daftar kontak lengkap (nama institusi, PIC, email, telepon, medsos, snapshot skor, status) untuk kebutuhan outreach tim lapangan.

---

## 10. Reporting (Laporan Eksekutif)

Menu: **Reporting**.  
Akses: **Admin** dan **Management**.

1. **Pembuatan Laporan**: Mengompilasi total cakupan organisasi, sebaran wilayah, institusi berpeluang tinggi, performa kampanye, dan rangkuman narasi AI.
2. **Ekspor Laporan**: Mengunduh ringkasan metrik dalam format CSV untuk bahan evaluasi manajemen pimpinan.

---

## 11. Discovery Universe (Otomatis & Terarah)

Menu: **Company Intelligence > Data Discovery** atau **Admin Panel > Discovery Triggers**.  
Akses: **Admin** dan **Business Analyst**.

Sistem menyediakan mesin discovery terpadu dengan kepatuhan tinggi:
- **Education Discovery**: Menemukan institusi pendidikan Indonesia secara bertahap dan terverifikasi dari jenjang PAUD, SD/MI, SMP/MTs, SMA/SMK/MA, Pesantren, hingga Perguruan Tinggi (Universitas, Institut, Politeknik, Sekolah Tinggi).
- **Community & Ormawa Discovery**: Menemukan komunitas olahraga (klub futsal, basket, running, lari, sepeda, esports) serta organisasi mahasiswa (BEM, DPM, HIMA, UKM).
- **Social Media Discovery & Enrichment**:
  - *Social Discovery*: Menemukan entitas baru berbasis kata kunci publik di platform Instagram, TikTok, Facebook, dan LinkedIn.
  - *Social Enrichment*: Melengkapi organisasi master yang belum memiliki media sosial dengan profil resmi dan sinyal kebutuhan jersey.
- **Provenance & Anti-Fabrication Guarantee**: Setiap hasil discovery mencatat URL sumber, platform, metode, confidence, dan timestamp. Tidak ada data fiktif atau klaim cakupan tanpa bukti.

---

## 12. Admin Panel & Mesin Automasi Terjadwal (Cron Jobs)

Menu: **Admin Panel > Scheduler & Cron** dan **Pipeline Monitoring**.  
Akses: **Admin Saja**.

### 12.1 10 Mesin Automasi Background Nyata
Sistem dilengkapi background runner nyata dengan 10 tugas otomatis:
1. `education_discovery`: Menjalankan discovery institusi pendidikan secara berkala.
2. `community_discovery`: Menemukan komunitas olahraga dan organisasi kemahasiswaan baru.
3. `social_discovery`: Menemukan kandidat entitas baru dari media sosial publik.
4. `social_enrichment`: Melengkapi organisasi master dengan profil dan sinyal media sosial.
5. `event_refresh`: Memperbarui data event turnamen dan status aktivitas.
6. `ai_product_scoring`: Menghitung atau memperbarui evaluasi AI Product Fit (Jersey).
7. `data_quality_check`: Memeriksa kelengkapan data kontak dan integritas rekaman.
8. `duplicate_detection`: Mendeteksi potensi duplikasi dan mendaftarkannya untuk ditinjau.
9. `retry_failed_jobs`: Mengulang otomatis pekerjaan latar belakang yang sempat terputus.
10. `cache_maintenance`: Membersihkan cache analitik dan mengoptimalkan performa kueri.

### 12.2 Kontrol Langsung & Metrik Eksekusi
Pada halaman **Scheduler & Cron**, Admin dapat:
- Melihat metrik eksekusi nyata: **Durasi (detik)**, **Jumlah Rekaman Diproses**, **Jumlah Berhasil**, **Jumlah Gagal**, **Ringkasan Error Terakhir**, serta jadwal **Next Run**.
- Menjalankan job seketika dengan menekan tombol **"Run Now"**.
- Mengulang job yang bermasalah dengan tombol **"Retry"**.
- Menghidupkan atau mematikan job dengan sakelar **"Toggle Status"**.

### 12.3 Pipeline Monitoring Real-Time
Memantau status server scheduler (`Running / Stopped`), antrean data masuk, serta log aktivitas pengguna secara real-time.

---

## 13. Skenario Prosedur Kerja Lapangan

### Skenario 1: Menemukan Target Kampanye Jersey untuk UKM dan Klub Futsal
1. **Marketing** membuka menu **Marketing Intelligence > Target Explorer**.
2. Masukkan filter:
   - *Cabang Olahraga*: `Futsal`.
   - *Subtipe*: `Klub Olahraga` atau `UKM Kampus`.
   - *Product Fit*: `High Fit` (Skor >= 75).
   - *Media Sosial*: Centang `Memiliki Instagram`.
3. Klik **Cari Target**.
4. Buat Kampanye baru di menu **Campaign Management** bernama *"Penawaran Jersey Futsal Mahasiswa Semester Ganjil"*.
5. Centang akun-akun futsal yang muncul di Target Explorer, lalu pilih *"Tambahkan ke Kampanye Futsal"*.
6. Buka detail kampanye dan klik **Export Lead List (CSV)** untuk dibagikan kepada tim sales/outreach lapangan.

### Skenario 2: Mengisi Kekosongan Data Sekolah & Universitas di Suatu Kota
1. **Business Analyst** atau **Admin** membuka **Admin Panel > Discovery Triggers** (atau **Data Discovery**).
2. Pada kartu *Education Discovery*, pilih wilayah target (misal: `Bandung`) dan jenjang `SMA/SMK` serta `Universitas`.
3. Klik **Jalankan Discovery**.
4. Sistem akan mencari sumber resmi publik, mengekstrak entitas, memeriksa duplikasi, dan menyimpannya ke *Master Organizations*.
5. Buka **Master Organizations** untuk meninjau entitas baru yang telah memiliki skor kesesuaian seragam/jersey.

### Skenario 3: Memperkaya Organisasi Master dengan Profil Media Sosial
1. Buka **Scheduler & Cron** di Admin Panel.
2. Klik **"Run Now"** pada job `social_enrichment`.
3. Sistem secara otomatis mencari profil publik Instagram/TikTok/Facebook/LinkedIn untuk organisasi yang belum memiliki kanal media sosial dan mengekstrak sinyal keterlibatan turnamen atau kebutuhan jersey.

---

## 14. Glosarium Istilah

| Istilah | Arti Sederhana |
|---|---|
| **Master Organization** | Profil institusi/perusahaan/komunitas tunggal yang menjadi Single Source of Truth. |
| **Prospect** | Layer penampung data masuk untuk validasi dan kompatibilitas sistem. |
| **Identity Resolution** | Proses otomatis yang mencocokkan entitas berdasarkan nama, domain, email, dan medsos agar tidak terjadi duplikasi. |
| **Duplicate Candidate** | Pasangan data yang memiliki kemiripan ambigu dan disimpan untuk ditinjau manual oleh pengguna tanpa penggabungan paksa. |
| **AI Product Fit** | Penilaian kecerdasan buatan terhadap seberapa besar kebutuhan organisasi terhadap produk jersey/custom teamwear. |
| **Product Signals** | Kata kunci publik yang mengindikasikan kebutuhan seragam, apparel, kit, atau jersey. |
| **Sport Signals** | Indikator cabang olahraga (futsal, sepak bola, basket, voli, lari, sepeda, esports). |
| **Activity Signals** | Indikator penyelenggaraan atau keikutsertaan turnamen, kejuaraan, liga, dies natalis, atau gathering. |
| **Campaign Target** | Organisasi master yang dipilih secara spesifik untuk dihubungi dalam suatu kampanye marketing beserta catatan snapshot skornya. |
| **Provenance** | Catatan rekam jejak asal-usul data (URL sumber, platform, waktu penemuan, dan tingkat keyakinan). |

---

## 15. Praktik Baik & Keamanan Sistem

1. **Kepatuhan Akses Publik**: Pengambilan data media sosial hanya menggunakan endpoint resmi atau pencarian web publik yang sah. **Tidak ada pembobolan login, pemalsuan identitas bot, bypass CAPTCHA, atau peretasan data pribadi.**
2. **Kebenaran Data (No Hallucination)**: AI tidak diperkenankan mengarang alamat, email, nomor kontak, maupun alasan kesesuaian produk jika datanya tidak tersedia. Jika data kosong, sistem akan menandainya sebagai `Review Needed` atau `Confidence Low`.
3. **Pemberian Hak Akses Minimum**: Pastikan staf marketing tidak diberikan role Admin agar konfigurasi automasi dan sistem database tetap terjaga.
4. **Verifikasi Sebelum Komunikasi**: Selalu lakukan verifikasi kesopanan dan nomor kontak sebelum melakukan penawaran massal kepada pihak institusi pendidikan maupun pengurus komunitas.