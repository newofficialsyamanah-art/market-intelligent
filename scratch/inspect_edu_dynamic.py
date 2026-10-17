import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app, db
from app.models import Organization

app = create_app()
with app.app_context():
    edu = Organization.query.filter(Organization.source_type == 'education_dynamic_discovery').all()
    print(f'Total education_dynamic_discovery: {len(edu)}')
    
    with_web = [e for e in edu if e.website]
    without_web = [e for e in edu if not e.website]
    print(f'With website: {len(with_web)}, Without website: {len(without_web)}')
    
    print('\nSample 15 with website:')
    for e in with_web[:15]:
        city = e.city or '-'
        print(f'{e.id} | {e.name[:40]:<40} | {city:<15} | {e.website}')
        
    print('\nSample 15 without website:')
    for e in without_web[:15]:
        city = e.city or '-'
        print(f'{e.id} | {e.name[:40]:<40} | {city:<15}')
