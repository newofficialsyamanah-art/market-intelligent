import sys
import os
sys.path.insert(0, os.path.abspath("."))

from app import create_app
from app.models import Event
from app.services.event_intelligence import EventIntelligenceService
import openpyxl

app = create_app()
with app.app_context():
    evs = Event.query.limit(5).all()
    stream = EventIntelligenceService.export_events_to_excel(evs, "Test Filter")
    stream.seek(0)
    wb = openpyxl.load_workbook(stream)
    ws = wb.active
    print("Sheet title:", ws.title)
    print("Max row:", ws.max_row, "Max col:", ws.max_column)
    for r in range(1, ws.max_row + 1):
        row_vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
        print(f"Row {r}:", row_vals[:6])

