path = r"d:\market_intelligence\app\templates\events\index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Top Action Toolbar
old_top_btns = """    <a href="{{ url_for('events.export') }}" class="btn btn-outline-success me-2">
      <i class="bi bi-file-earmark-spreadsheet me-1"></i> Export Partisipan CSV
    </a>"""

new_top_btns = """    <button type="button" class="btn btn-success me-2 shadow-sm" data-bs-toggle="modal" data-bs-target="#modalExportExcel">
      <i class="bi bi-file-earmark-excel me-1"></i> Export Excel
    </button>
    <a href="{{ url_for('events.export') }}" class="btn btn-outline-success me-2">
      <i class="bi bi-file-earmark-spreadsheet me-1"></i> Partisipan CSV
    </a>"""

content = content.replace(old_top_btns, new_top_btns)

# 2. Update Filter Bar (Year + Month)
old_year_select = """      <div class="col-md-2">
        <select name="year" class="form-select fw-semibold text-primary">
          <option value="">Semua Tahun</option>
          <option value="2027" {% if filters.year == '2027' %}selected{% endif %}>Tahun 2027</option>
          <option value="2026" {% if filters.year == '2026' %}selected{% endif %}>Tahun 2026</option>
        </select>
      </div>"""

new_year_select = """      <div class="col-md-2">
        <select name="year" class="form-select fw-semibold text-primary">
          <option value="">Semua Tahun</option>
          {% for y in available_years %}
          <option value="{{ y }}" {% if filters.year == y|string %}selected{% endif %}>Tahun {{ y }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-2">
        <select name="month" class="form-select">
          <option value="">Semua Bulan</option>
          <option value="1" {% if filters.month == '1' %}selected{% endif %}>Januari</option>
          <option value="2" {% if filters.month == '2' %}selected{% endif %}>Februari</option>
          <option value="3" {% if filters.month == '3' %}selected{% endif %}>Maret</option>
          <option value="4" {% if filters.month == '4' %}selected{% endif %}>April</option>
          <option value="5" {% if filters.month == '5' %}selected{% endif %}>Mei</option>
          <option value="6" {% if filters.month == '6' %}selected{% endif %}>Juni</option>
          <option value="7" {% if filters.month == '7' %}selected{% endif %}>Juli</option>
          <option value="8" {% if filters.month == '8' %}selected{% endif %}>Agustus</option>
          <option value="9" {% if filters.month == '9' %}selected{% endif %}>September</option>
          <option value="10" {% if filters.month == '10' %}selected{% endif %}>Oktober</option>
          <option value="11" {% if filters.month == '11' %}selected{% endif %}>November</option>
          <option value="12" {% if filters.month == '12' %}selected{% endif %}>Desember</option>
        </select>
      </div>"""

content = content.replace(old_year_select, new_year_select)

# 3. Add Modal Export Excel
modal_export_html = """<!-- Modal Export Data Event ke Excel -->
<div class="modal fade" id="modalExportExcel" tabindex="-1" aria-labelledby="modalExportExcelLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content border-0 shadow">
      <div class="modal-header bg-success text-white">
        <h5 class="modal-title d-flex align-items-center gap-2" id="modalExportExcelLabel">
          <i class="bi bi-file-earmark-excel fs-4"></i>
          <span>Export Data Event ke Excel (.xlsx)</span>
        </h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Tutup"></button>
      </div>
      <form action="{{ url_for('events.export_excel') }}" method="GET">
        <div class="modal-body p-4">
          <div class="alert alert-success-subtle border border-success-subtle text-dark small mb-3">
            <i class="bi bi-info-circle me-1 text-success"></i>
            File Excel diformat profesional lengkap dengan nama event, tanggal pelaksanaan presisi, status jadwal, venue/gedung, kota, skor relevansi, dan kontak panitia.
          </div>

          <!-- Opsi Tahun -->
          <div class="mb-3">
            <label class="form-label fw-bold text-dark">Berdasarkan Tahun</label>
            <select name="year" class="form-select">
              <option value="">Semua Tahun (Semua Data)</option>
              {% for y in available_years %}
              <option value="{{ y }}" {% if filters.year == y|string %}selected{% endif %}>Tahun {{ y }}</option>
              {% endfor %}
            </select>
          </div>

          <!-- Opsi Bulan -->
          <div class="mb-3">
            <label class="form-label fw-bold text-dark">Berdasarkan Bulan (Opsional)</label>
            <select name="month" class="form-select">
              <option value="">Semua Bulan</option>
              <option value="1" {% if filters.month == '1' %}selected{% endif %}>Januari</option>
              <option value="2" {% if filters.month == '2' %}selected{% endif %}>Februari</option>
              <option value="3" {% if filters.month == '3' %}selected{% endif %}>Maret</option>
              <option value="4" {% if filters.month == '4' %}selected{% endif %}>April</option>
              <option value="5" {% if filters.month == '5' %}selected{% endif %}>Mei</option>
              <option value="6" {% if filters.month == '6' %}selected{% endif %}>Juni</option>
              <option value="7" {% if filters.month == '7' %}selected{% endif %}>Juli</option>
              <option value="8" {% if filters.month == '8' %}selected{% endif %}>Agustus</option>
              <option value="9" {% if filters.month == '9' %}selected{% endif %}>September</option>
              <option value="10" {% if filters.month == '10' %}selected{% endif %}>Oktober</option>
              <option value="11" {% if filters.month == '11' %}selected{% endif %}>November</option>
              <option value="12" {% if filters.month == '12' %}selected{% endif %}>Desember</option>
            </select>
          </div>

          <!-- Opsi Tanggal Spesifik -->
          <div class="mb-3">
            <label class="form-label fw-bold text-dark">Atau Rentang Tanggal Spesifik</label>
            <div class="row g-2">
              <div class="col-6">
                <input type="date" name="start_date_from" class="form-control" title="Mulai Dari" value="{{ filters.start_date_from }}">
              </div>
              <div class="col-6">
                <input type="date" name="start_date_to" class="form-control" title="Sampai Tanggal" value="{{ filters.start_date_to }}">
              </div>
            </div>
            <small class="text-muted">Kosongkan jika ingin mengunduh berdasarkan tahun atau bulan.</small>
          </div>

          <!-- Teruskan Filter yang Sedang Aktif -->
          <input type="hidden" name="q" value="{{ filters.q }}">
          <input type="hidden" name="city" value="{{ filters.city }}">
          <input type="hidden" name="province" value="{{ filters.province }}">
          <input type="hidden" name="event_type" value="{{ filters.event_type }}">
          <input type="hidden" name="relevance" value="{{ filters.relevance }}">
          <input type="hidden" name="sport" value="{{ filters.sport }}">
          <input type="hidden" name="status" value="{{ filters.status }}">
          <input type="hidden" name="organizer" value="{{ filters.organizer }}">
        </div>
        <div class="modal-footer bg-light">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Batal</button>
          <button type="submit" class="btn btn-success d-inline-flex align-items-center gap-2">
            <i class="bi bi-download"></i>
            <span>Download Excel (.xlsx)</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
"""

# Place modalExportExcel before modalDiscoverEvents
content = content.replace("<!-- Modal Discovery Event AI Se-Indonesia -->", modal_export_html + "\n<!-- Modal Discovery Event AI Se-Indonesia -->")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully updated app/templates/events/index.html with Export Excel button, modal, and dynamic year/month filters!")

