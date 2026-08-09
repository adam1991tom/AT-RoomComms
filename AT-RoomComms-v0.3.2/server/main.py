import os, sqlite3, hashlib, hmac, secrets, uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

VERSION='0.3.2'
DATA=Path(os.getenv('ROOMCOMMS_DATA','/data')); DB=DATA/'roomcomms.db'; UP=DATA/'uploads'
DATA.mkdir(parents=True,exist_ok=True); UP.mkdir(exist_ok=True)
app=FastAPI(title='AT RoomComms',version=VERSION)
app.mount('/static',StaticFiles(directory=Path(__file__).parent/'static'),name='static')

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def pw_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),200000).hex()
    return f'{salt}${digest}'
def pw_ok(password,stored):
    try:
        salt,digest=stored.split('$',1)
        return hmac.compare_digest(pw_hash(password,salt),stored)
    except: return False

def init():
    with db() as c:
        c.executescript('''
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,display_name TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,account_id INTEGER NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS operators(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,short_name TEXT DEFAULT '',current_status TEXT DEFAULT 'closed',enabled INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,client TEXT DEFAULT '',event_color TEXT DEFAULT '#8b5cf6',starts_at TEXT DEFAULT '',ends_at TEXT DEFAULT '',event_status TEXT DEFAULT 'scheduled',archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS event_rooms(event_id INTEGER NOT NULL,room_id INTEGER NOT NULL,operator_name TEXT DEFAULT '',PRIMARY KEY(event_id,room_id),FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,role TEXT,room_id INTEGER,event_id INTEGER,operator TEXT,online_status TEXT,last_heartbeat TEXT,app_version TEXT);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,scope TEXT,scope_id INTEGER,sender TEXT,body TEXT,priority TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY AUTOINCREMENT,message_id INTEGER,original_name TEXT,stored_name TEXT,mime_type TEXT,size INTEGER);
CREATE TABLE IF NOT EXISTS help_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id INTEGER,room_id INTEGER,room_name TEXT,requested_by TEXT,category TEXT,description TEXT,priority TEXT,status TEXT,assigned_to TEXT,created_at TEXT,acknowledged_at TEXT,resolved_at TEXT);
''')
        cols=[r['name'] for r in c.execute('PRAGMA table_info(event_rooms)')]
        if 'operator_name' not in cols: c.execute("ALTER TABLE event_rooms ADD COLUMN operator_name TEXT DEFAULT ''")
        c.execute("INSERT OR IGNORE INTO settings VALUES('venue_name','Harrogate Convention Centre')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('control_centre_name','Speaker Preview')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('attachment_limit_mb','25')")
        if not c.execute("SELECT 1 FROM accounts WHERE username='adam'").fetchone():
            c.execute('INSERT INTO accounts(username,password_hash,display_name,role) VALUES(?,?,?,?)',('adam',pw_hash('changeme'),'Adam','admin'))
        if not c.execute("SELECT 1 FROM accounts WHERE username='speakerpreview'").fetchone():
            c.execute('INSERT INTO accounts(username,password_hash,display_name,role) VALUES(?,?,?,?)',('speakerpreview',pw_hash('changeme'),'Speaker Preview','speaker_preview'))
        if c.execute('SELECT COUNT(*) n FROM rooms').fetchone()['n']==0:
            rooms=[("Queen's Suite 1",'QS1','ready'),("Queen's Suite 2",'QS2','live'),("Queen's Suite 3",'QS3','technical_issue'),("Queen's Suite 4",'QS4','setting_up'),("Queen's Suite 5",'QS5','ready'),("Queen's Suite 6",'QS6','rehearsal'),('Auditorium','AUD','live')]
            c.executemany('INSERT INTO rooms(name,short_name,current_status) VALUES(?,?,?)',rooms)
init()

def require_auth(authorization:str|None):
    if not authorization or not authorization.lower().startswith('bearer '): raise HTTPException(401,'Login required')
    token=authorization.split(' ',1)[1].strip()
    with db() as c:
        r=c.execute('SELECT a.id,a.username,a.display_name,a.role,a.active FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token=?',(token,)).fetchone()
    if not r or not r['active']: raise HTTPException(401,'Session invalid')
    return dict(r)
def require_manager(auth):
    if auth['role'] not in ('admin','speaker_preview'): raise HTTPException(403,'Manager permission required')
def require_admin(auth):
    if auth['role']!='admin': raise HTTPException(403,'Admin permission required')

class Login(BaseModel): username:str; password:str
class EventIn(BaseModel): name:str; client:str=''; event_color:str='#8b5cf6'; starts_at:str=''; ends_at:str=''; event_status:str='scheduled'
class RoomIn(BaseModel): name:str; short_name:str=''; current_status:str='closed'
class OperatorIn(BaseModel): name:str
class AccountIn(BaseModel): username:str; password:str; display_name:str; role:str='speaker_preview'
class PasswordIn(BaseModel): password:str
class MessageIn(BaseModel): scope:str; scope_id:int|None=None; sender:str; body:str=''; priority:str='normal'

@app.get('/',response_class=HTMLResponse)
def home(): return HTMLResponse((Path(__file__).parent/'static'/'index.html').read_text())
@app.get('/api/health')
def health(): return {'status':'ok','version':VERSION}

@app.post('/api/auth/login')
def login(x:Login):
    with db() as c:
        a=c.execute('SELECT * FROM accounts WHERE username=? AND active=1',(x.username,)).fetchone()
        if not a or not pw_ok(x.password,a['password_hash']): raise HTTPException(401,'Invalid username or password')
        token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,account_id,created_at) VALUES(?,?,?)',(token,a['id'],now()))
    return {'token':token,'user':{'id':a['id'],'username':a['username'],'display_name':a['display_name'],'role':a['role']}}
@app.get('/api/auth/me')
def me(authorization:str|None=Header(default=None)): return require_auth(authorization)
@app.post('/api/auth/logout')
def logout(authorization:str|None=Header(default=None)):
    if authorization and authorization.lower().startswith('bearer '):
        with db() as c:c.execute('DELETE FROM sessions WHERE token=?',(authorization.split(' ',1)[1].strip(),))
    return {'ok':True}

@app.get('/api/bootstrap')
def boot(authorization:str|None=Header(default=None)):
    auth=require_auth(authorization)
    with db() as c:
        return {'version':VERSION,'me':auth,'settings':{r['key']:r['value'] for r in c.execute('SELECT * FROM settings')},
        'rooms':[dict(r) for r in c.execute('SELECT * FROM rooms WHERE enabled=1 ORDER BY name')],
        'events':[dict(r) for r in c.execute('SELECT * FROM events WHERE archived=0 ORDER BY starts_at,name')],
        'event_rooms':[dict(r) for r in c.execute('SELECT * FROM event_rooms')],
        'operators':[dict(r) for r in c.execute('SELECT * FROM operators WHERE active=1 ORDER BY name')],
        'devices':[dict(r) for r in c.execute('SELECT * FROM devices ORDER BY name')],
        'help_requests':[dict(r) for r in c.execute("SELECT * FROM help_requests WHERE status NOT IN ('resolved','cancelled') ORDER BY id DESC")]}

@app.post('/api/events')
async def create_event(x:EventIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c: eid=c.execute('INSERT INTO events(name,client,event_color,starts_at,ends_at,event_status) VALUES(?,?,?,?,?,?)',(x.name,x.client,x.event_color,x.starts_at,x.ends_at,x.event_status)).lastrowid
    return {'id':eid}
@app.patch('/api/events/{eid}')
async def update_event(eid:int,x:EventIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:c.execute('UPDATE events SET name=?,client=?,event_color=?,starts_at=?,ends_at=?,event_status=? WHERE id=?',(x.name,x.client,x.event_color,x.starts_at,x.ends_at,x.event_status,eid))
    return {'ok':True}
@app.delete('/api/events/{eid}')
async def delete_event(eid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:c.execute('DELETE FROM events WHERE id=?',(eid,))
    return {'ok':True}

@app.post('/api/rooms')
async def create_room(x:RoomIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:
        try: rid=c.execute('INSERT INTO rooms(name,short_name,current_status) VALUES(?,?,?)',(x.name,x.short_name,x.current_status)).lastrowid
        except sqlite3.IntegrityError: raise HTTPException(409,'Room already exists')
    return {'id':rid}
@app.patch('/api/rooms/{rid}')
async def update_room(rid:int,x:RoomIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:c.execute('UPDATE rooms SET name=?,short_name=?,current_status=? WHERE id=?',(x.name,x.short_name,x.current_status,rid))
    return {'ok':True}
@app.delete('/api/rooms/{rid}')
async def delete_room(rid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:c.execute('UPDATE rooms SET enabled=0 WHERE id=?',(rid,)); c.execute('DELETE FROM event_rooms WHERE room_id=?',(rid,))
    return {'ok':True}

@app.post('/api/events/{eid}/rooms/{rid}')
async def add_event_room(eid:int,rid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a); operator=(p.get('operator_name') or '').strip()
    with db() as c:c.execute('INSERT INTO event_rooms(event_id,room_id,operator_name) VALUES(?,?,?) ON CONFLICT(event_id,room_id) DO UPDATE SET operator_name=excluded.operator_name',(eid,rid,operator))
    return {'ok':True}
@app.patch('/api/events/{eid}/rooms/{rid}')
async def edit_event_room(eid:int,rid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:c.execute('UPDATE event_rooms SET operator_name=? WHERE event_id=? AND room_id=?',((p.get('operator_name') or '').strip(),eid,rid))
    return {'ok':True}
@app.delete('/api/events/{eid}/rooms/{rid}')
async def remove_event_room(eid:int,rid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:c.execute('DELETE FROM event_rooms WHERE event_id=? AND room_id=?',(eid,rid))
    return {'ok':True}

@app.post('/api/operators')
def create_operator(x:OperatorIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:
        try: oid=c.execute('INSERT INTO operators(name) VALUES(?)',(x.name.strip(),)).lastrowid
        except sqlite3.IntegrityError:
            c.execute('UPDATE operators SET active=1 WHERE name=?',(x.name.strip(),)); oid=c.execute('SELECT id FROM operators WHERE name=?',(x.name.strip(),)).fetchone()['id']
    return {'id':oid}
@app.delete('/api/operators/{oid}')
def delete_operator(oid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_manager(a)
    with db() as c:c.execute('UPDATE operators SET active=0 WHERE id=?',(oid,))
    return {'ok':True}

@app.get('/api/accounts')
def accounts(authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_admin(a)
    with db() as c:return [dict(r) for r in c.execute('SELECT id,username,display_name,role,active FROM accounts ORDER BY username')]
@app.post('/api/accounts')
def create_account(x:AccountIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_admin(a)
    if x.role not in ('admin','speaker_preview'): raise HTTPException(400,'Invalid role')
    with db() as c:
        try: aid=c.execute('INSERT INTO accounts(username,password_hash,display_name,role) VALUES(?,?,?,?)',(x.username.strip(),pw_hash(x.password),x.display_name.strip(),x.role)).lastrowid
        except sqlite3.IntegrityError: raise HTTPException(409,'Username already exists')
    return {'id':aid}
@app.patch('/api/accounts/{aid}/password')
def account_password(aid:int,x:PasswordIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_admin(a)
    with db() as c:c.execute('UPDATE accounts SET password_hash=? WHERE id=?',(pw_hash(x.password),aid)); c.execute('DELETE FROM sessions WHERE account_id=?',(aid,))
    return {'ok':True}
@app.delete('/api/accounts/{aid}')
def disable_account(aid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_admin(a)
    if aid==a['id']: raise HTTPException(400,'Cannot disable your own account')
    with db() as c:c.execute('UPDATE accounts SET active=0 WHERE id=?',(aid,)); c.execute('DELETE FROM sessions WHERE account_id=?',(aid,))
    return {'ok':True}

@app.patch('/api/settings')
def settings_update(p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization); require_admin(a)
    allowed={'venue_name','control_centre_name','attachment_limit_mb'}
    with db() as c:
        for k,v in p.items():
            if k in allowed:c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
    return {'ok':True}

@app.get('/api/messages')
def messages(scope:str,scope_id:int|None=None,authorization:str|None=Header(default=None)):
    require_auth(authorization)
    with db() as c:
        rows=c.execute("SELECT * FROM messages WHERE scope='venue' ORDER BY id DESC LIMIT 200") if scope=='venue' else c.execute('SELECT * FROM messages WHERE scope=? AND scope_id=? ORDER BY id DESC LIMIT 200',(scope,scope_id)); out=[]
        for r in reversed(rows.fetchall()):
            d=dict(r); d['attachments']=[dict(x) for x in c.execute('SELECT * FROM attachments WHERE message_id=?',(r['id'],))]; out.append(d)
        return out
@app.post('/api/messages')
async def add_message(x:MessageIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization)
    sender=x.sender.strip() or a['display_name']
    with db() as c: mid=c.execute('INSERT INTO messages(scope,scope_id,sender,body,priority,created_at) VALUES(?,?,?,?,?,?)',(x.scope,x.scope_id,sender,x.body,x.priority,now())).lastrowid
    return {'id':mid}
@app.post('/api/messages/{mid}/attachments')
async def attach(mid:int,file:UploadFile=File(...),authorization:str|None=Header(default=None)):
    require_auth(authorization)
    with db() as c: lim=int(c.execute("SELECT value FROM settings WHERE key='attachment_limit_mb'").fetchone()['value'])
    safe=''.join(ch for ch in file.filename if ch.isalnum() or ch in '._- ')[:180] or 'file'; stored=uuid.uuid4().hex+'_'+safe; dest=UP/stored; size=0
    with dest.open('wb') as f:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            if size>lim*1024*1024: f.close(); dest.unlink(missing_ok=True); raise HTTPException(413,f'{lim}MB limit')
            f.write(chunk)
    with db() as c:c.execute('INSERT INTO attachments(message_id,original_name,stored_name,mime_type,size) VALUES(?,?,?,?,?)',(mid,file.filename,stored,file.content_type or '',size))
    return {'ok':True}
@app.get('/api/attachments/{aid}')
def get_attachment(aid:int,authorization:str|None=Header(default=None)):
    require_auth(authorization)
    with db() as c:r=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
    if not r: raise HTTPException(404)
    return FileResponse(UP/r['stored_name'],media_type=r['mime_type'] or 'application/octet-stream',filename=r['original_name'])

@app.websocket('/ws')
async def ws(w:WebSocket):
    await w.accept()
    try:
        while True: await w.receive_text()
    except WebSocketDisconnect: pass
