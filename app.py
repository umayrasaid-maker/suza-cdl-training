"""CDL Training Hub: Flask + SQLite. Set ADMIN_KEY and SECRET_KEY in production."""
import os, sqlite3, json, hmac
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

ROOT = Path(__file__).parent
DB = Path(os.environ.get('CDL_DB_PATH', ROOT / 'data' / 'cdl.sqlite3'))
ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024

def conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with conn() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS trainings (id INTEGER PRIMARY KEY, date TEXT NOT NULL, topic TEXT NOT NULL, audience TEXT NOT NULL, original_hours INTEGER, output TEXT, facilitator TEXT, status TEXT NOT NULL DEFAULT 'open', capacity INTEGER NOT NULL DEFAULT 40, venue TEXT NOT NULL DEFAULT 'CDL Room', notes TEXT NOT NULL DEFAULT '');
          CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL, date TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        ''')
        if db.execute('SELECT COUNT(*) FROM trainings').fetchone()[0] == 0:
            for item in json.loads((ROOT/'data'/'trainings.json').read_text()):
                db.execute('INSERT INTO trainings (id,date,topic,audience,original_hours,output,facilitator,venue) VALUES (?,?,?,?,?,?,?,?)', [*item, 'CDL Room'])
        name_map = {'Salim': 'Salim Juma', 'Umayra': 'Umayra M. Said', 'Ramadhan': 'Ramadhan Rai', 'Salum Simba': 'Salim Simba', 'ALL': 'Salim Juma, Umayra M. Said, Ramadhan Rai and Salim Simba'}
        for old, new in name_map.items():
            db.execute('UPDATE trainings SET facilitator=? WHERE facilitator=?', (new, old))
        db.execute("UPDATE trainings SET venue='CDL Room' WHERE venue IS NULL OR venue='' OR venue='Venue to be confirmed'")
        if db.execute('SELECT COUNT(*) FROM announcements').fetchone()[0] == 0:
            db.execute('INSERT INTO announcements (title,body,date) VALUES (?,?,?)', ('CDL Friday training programme', 'Explore the CDL 2026–2027 programme. Friday sessions run from 2:00 PM to 4:00 PM at CDL Room. Any extensions for longer workshops will be announced separately.', '2026-11-17'))

@app.get('/')
def home(): return send_from_directory(ROOT/'static', 'index.html')

@app.get('/api/trainings')
def trainings():
    with conn() as db:
        rows = db.execute('SELECT * FROM trainings ORDER BY date').fetchall()
    return jsonify([dict(x) for x in rows])

@app.get('/api/announcements')
def announcements():
    with conn() as db:
        return jsonify([dict(x) for x in db.execute('SELECT * FROM announcements WHERE active=1 ORDER BY date DESC, id DESC')])

def clean(value, limit): return str(value or '').strip()[:limit]

def authorized():
    supplied = request.headers.get('X-Admin-Key','')
    return bool(ADMIN_KEY) and hmac.compare_digest(supplied, ADMIN_KEY)

def denied(): return jsonify(error='Admin access denied. Configure ADMIN_KEY on the server.'),401

@app.patch('/api/admin/trainings/<int:tid>')
def edit_training(tid):
    if not authorized(): return denied()
    data=request.get_json(silent=True) or {}; allowed={'status','venue','notes'}
    fields={k:v for k,v in data.items() if k in allowed}
    if not fields:return jsonify(error='No editable fields provided.'),400
    if 'status' in fields and fields['status'] not in ('open','closed','cancelled'):return jsonify(error='Invalid status.'),400
    for k in ('venue','notes'):
        if k in fields:fields[k]=clean(fields[k],300)
    with conn() as db:
        cur=db.execute('UPDATE trainings SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?',(*fields.values(),tid))
        if not cur.rowcount:return jsonify(error='Not found.'),404
    return jsonify(success=True)

@app.post('/api/admin/announcements')
def add_announcement():
    if not authorized(): return denied()
    data=request.get_json(silent=True) or {}
    title=clean(data.get('title'),140);body=clean(data.get('body'),1000)
    if not title or not body:return jsonify(error='Title and text are required.'),400
    with conn() as db:
        db.execute('INSERT INTO announcements(title,body,date) VALUES (?,?,?)',(title,body,datetime.now(timezone.utc).date().isoformat()))
    return jsonify(success=True),201

@app.delete('/api/admin/announcements/<int:aid>')
def hide_announcement(aid):
    if not authorized():return denied()
    with conn() as db: db.execute('UPDATE announcements SET active=0 WHERE id=?',(aid,))
    return jsonify(success=True)

init()
if __name__=='__main__':
    app.run(host=os.environ.get('HOST','127.0.0.1'),port=int(os.environ.get('PORT',5000)),debug=False)
