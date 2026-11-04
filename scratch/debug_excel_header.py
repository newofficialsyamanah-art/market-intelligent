import sys
import os
sys.path.insert(0, os.path.abspath("."))

from app import create_app
from app.models import Event
from app.services.event_intelligence import EventIntelligenceService
import openpyxl

app = create_app()
with app.app_context():
    evs = Event.query.limit(3).all()
    stream = EventIntelligenceService.export_events_to_excel(evs, "Test Filter")
    stream.seek(0)
    wb = openpyxl.load_workbook(stream)
    ws = wb.active
    print("=== DUMP ROWS 1-3 ===")
    for r in range(1, 4):
        vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
        print(f"Row {r} (len {len(vals)}):", vals)
    
    # Check Row 1 styling
    cell_a1 = ws.cell(1, 1)
    print("A1 value:", repr(cell_a1.value))
    print("A1 font color:", cell_a1.font.color.rgb if cell_a1.font and cell_a1.font.color else None)
    print("A1 fill type:", cell_a1.fill.fill_type if cell_a1.fill else None)
    print("A1 start_color:", cell_a1.fill.start_color.rgb if cell_a1.fill and cell_a1.fill.start_color else None)
    print("A1 fgColor:", getattr(cell_a1.fill, 'fgColor', None))

