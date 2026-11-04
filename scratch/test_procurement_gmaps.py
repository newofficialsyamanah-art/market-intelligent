import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app import create_app, db
from app.models import User
from bs4 import BeautifulSoup

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    user = User.query.filter_by(role="procurement").first()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    resp_post = client.post('/procurement/gmaps-search', data={
        "query": "toko kain",
        "location": "Bandung",
        "limit": 5
    }, follow_redirects=True)
    
    soup = BeautifulSoup(resp_post.data, "html.parser")
    for al in soup.find_all(class_="alert"):
        print("TAMPILAN NOTIFIKASI DI LAYAR:")
        print(al.get_text(strip=True))

