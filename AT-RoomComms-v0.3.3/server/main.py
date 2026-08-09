import os, sqlite3, hashlib, hmac, secrets, uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

VERSION='0.3.3'
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
        salt,_=stored.split('$',1)
        return hmac.compare_digest(pw_hash(password,salt),stored)
    except: return False

def setting(c,key,default=''):
    r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return r['value'] if r else default

def setup_complete(c=None):
    own=c is None
    c=c or db()
    try: return setting(c,'setup_complete','0')=='1'
    finally:
        if own:c.close()

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
        if 'operator_name' not in cols:c.execute("ALTER TABLE event_rooms ADD COLUMN operator_name TEXT DEFAULT ''")
        c.execute("INSERT OR IGNORE INTO settings VALUES('venue_name','Harrogate Convention Centre')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('control_centre_name','Speaker Preview')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('attachment_limit_mb','25')")
        # Deliberately do NOT seed passwords. Existing v0.3.2 installations have no
        # setup_complete key, so the first-run wizard will repair the privileged accounts.
init()

class SetupIn(BaseModel):
    venue_name:str='Harrogate Convention Centre'
    control_centre_name:str='Speaker Preview'
    admin_display_name:str
    admin_username:str
    admin_password:str
    speaker_display_name:str='Speaker Preview'
    speaker_username:str='speakerpreview'
    speaker_password:str
class Login(BaseModel): username:str; password:str
class EventIn(BaseModel): name:str; client:str=''; event_color:str='#8b5cf6'; starts_at:str=''; ends_at:str=''; event_status:str='scheduled'
class RoomIn(BaseModel): name:str; short_name:str=''; current_status:str='closed'
class OperatorIn(BaseModel): name:str
class AccountIn(BaseModel): username:str; password:str; display_name:str; role:str='speaker_preview'
class PasswordIn(BaseModel): password:str
class MessageIn(BaseModel): scope:str; scope_id:int|None=None; sender:str=''; body:str=''; priority:str='normal'
class DeviceIn(BaseModel): name:str; role:str='general'; room_id:int|None=None; event_id:int|None=None; operator:str=''; app_version:str=''
class HelpIn(BaseModel): event_id:int|None=None; room_id:int|None=None; requested_by:str; category:str; description:str; priority:str='important'

def require_auth(authorization:str|None):
    if not setup_complete():raise HTTPException(503,'First run setup required')
    if not authorization or not authorization.lower().startswith('bearer '):raise HTTPException(401,'Login required')
    token=authorization.split(' ',1)[1].strip()
    with db() as c:r=c.execute('SELECT a.id,a.username,a.display_name,a.role,a.active FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token=?',(token,)).fetchone()
    if not r or not r['active']:raise HTTPException(401,'Session invalid')
    return dict(r)
def require_manager(a):
    if a['role'] not in ('admin','speaker_preview'):raise HTTPException(403,'Manager permission required')
def require_admin(a):
    if a['role']!='admin':raise HTTPException(403,'Administrator permission required')

@app.get('/',response_class=HTMLResponse)
def home():return HTMLResponse((Path(__file__).parent/'static'/'index.html').read_text(encoding='utf-8'))
@app.get('/api/health')
def health():return {'status':'ok','version':VERSION}
@app.get('/api/setup/status')
def setup_status():return {'needs_setup':not setup_complete(),'version':VERSION}
@app.post('/api/setup/complete')
def finish_setup(x:SetupIn):
    with db() as c:
        if setup_complete(c):raise HTTPException(403,'Setup already completed')
        au=x.admin_username.strip(); an=x.admin_display_name.strip(); su=x.speaker_username.strip(); sn=x.speaker_display_name.strip()
        if not au or not an or not su or not sn:raise HTTPException(400,'All names and usernames are required')
        if au.lower()==su.lower():raise HTTPException(400,'Admin and Speaker Preview usernames must be different')
        if len(x.admin_password)<8 or len(x.speaker_password)<8:raise HTTPException(400,'Passwords must be at least 8 characters')
        # Reset only privileged auth records. Venue/event/room/message data is preserved.
        c.execute('DELETE FROM sessions')
        c.execute('DELETE FROM accounts')
        c.execute('INSERT INTO accounts(username,password_hash,display_name,role,active) VALUES(?,?,?,?,1)',(au,pw_hash(x.admin_password),an,'admin'))
        aid=c.execute('SELECT id FROM accounts WHERE username=?',(au,)).fetchone()['id']
        c.execute('INSERT INTO accounts(username,password_hash,display_name,role,active) VALUES(?,?,?,?,1)',(su,pw_hash(x.speaker_password),sn,'speaker_preview'))
        for k,v in [('venue_name',x.venue_name.strip() or 'Venue'),('control_centre_name',x.control_centre_name.strip() or 'Speaker Preview'),('setup_complete','1')]:
            c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,v))
        token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions(token,account_id,created_at) VALUES(?,?,?)',(token,aid,now()))
    return {'ok':True,'token':token,'user':{'id':aid,'username':au,'display_name':an,'role':'admin'}}

@app.post('/api/auth/login')
def login(x:Login):
    if not setup_complete():raise HTTPException(503,'First run setup required')
    with db() as c:
        a=c.execute('SELECT * FROM accounts WHERE lower(username)=lower(?) AND active=1',(x.username.strip(),)).fetchone()
        if not a or not pw_ok(x.password,a['password_hash']):raise HTTPException(401,'Invalid username or password')
        token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions(token,account_id,created_at) VALUES(?,?,?)',(token,a['id'],now()))
    return {'token':token,'user':{'id':a['id'],'username':a['username'],'display_name':a['display_name'],'role':a['role']}}
@app.post('/api/auth/logout')
def logout(authorization:str|None=Header(default=None)):
    if authorization and authorization.lower().startswith('bearer '):
        with db() as c:c.execute('DELETE FROM sessions WHERE token=?',(authorization.split(' ',1)[1].strip(),))
    return {'ok':True}
@app.get('/api/auth/me')
def me(authorization:str|None=Header(default=None)):return require_auth(authorization)

@app.get('/api/bootstrap')
def bootstrap(authorization:str|None=Header(default=None)):
    a=require_auth(authorization)
    with db() as c:return {'version':VERSION,'me':a,'settings':{r['key']:r['value'] for r in c.execute('SELECT * FROM settings')},'rooms':[dict(r) for r in c.execute('SELECT * FROM rooms WHERE enabled=1 ORDER BY name')],'events':[dict(r) for r in c.execute('SELECT * FROM events WHERE archived=0 ORDER BY starts_at,name')],'event_rooms':[dict(r) for r in c.execute('SELECT * FROM event_rooms')],'operators':[dict(r) for r in c.execute('SELECT * FROM operators WHERE active=1 ORDER BY name')],'devices':[dict(r) for r in c.execute('SELECT * FROM devices ORDER BY name')],'help_requests':[dict(r) for r in c.execute("SELECT * FROM help_requests WHERE status NOT IN ('resolved','cancelled') ORDER BY id DESC")]}

@app.post('/api/events')
def event_create(x:EventIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:eid=c.execute('INSERT INTO events(name,client,event_color,starts_at,ends_at,event_status) VALUES(?,?,?,?,?,?)',(x.name.strip(),x.client.strip(),x.event_color,x.starts_at,x.ends_at,x.event_status)).lastrowid
    return {'id':eid}
@app.patch('/api/events/{eid}')
def event_update(eid:int,x:EventIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE events SET name=?,client=?,event_color=?,starts_at=?,ends_at=?,event_status=? WHERE id=?',(x.name.strip(),x.client.strip(),x.event_color,x.starts_at,x.ends_at,x.event_status,eid))
    return {'ok':True}
@app.delete('/api/events/{eid}')
def event_delete(eid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('DELETE FROM event_rooms WHERE event_id=?',(eid,));c.execute('DELETE FROM events WHERE id=?',(eid,))
    return {'ok':True}

@app.post('/api/rooms')
def room_create(x:RoomIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:
        try:rid=c.execute('INSERT INTO rooms(name,short_name,current_status) VALUES(?,?,?)',(x.name.strip(),x.short_name.strip(),x.current_status)).lastrowid
        except sqlite3.IntegrityError:raise HTTPException(409,'Room already exists')
    return {'id':rid}
@app.patch('/api/rooms/{rid}')
def room_update(rid:int,x:RoomIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE rooms SET name=?,short_name=?,current_status=? WHERE id=?',(x.name.strip(),x.short_name.strip(),x.current_status,rid))
    return {'ok':True}
@app.delete('/api/rooms/{rid}')
def room_delete(rid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('DELETE FROM event_rooms WHERE room_id=?',(rid,));c.execute('UPDATE rooms SET enabled=0 WHERE id=?',(rid,))
    return {'ok':True}
@app.patch('/api/rooms/{rid}/status')
def room_status(rid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE rooms SET current_status=? WHERE id=?',(p.get('status','closed'),rid))
    return {'ok':True}

@app.post('/api/events/{eid}/rooms/{rid}')
def event_room_add(eid:int,rid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('INSERT INTO event_rooms(event_id,room_id,operator_name) VALUES(?,?,?) ON CONFLICT(event_id,room_id) DO UPDATE SET operator_name=excluded.operator_name',(eid,rid,(p.get('operator_name') or '').strip()))
    return {'ok':True}
@app.patch('/api/events/{eid}/rooms/{rid}')
def event_room_update(eid:int,rid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE event_rooms SET operator_name=? WHERE event_id=? AND room_id=?',((p.get('operator_name') or '').strip(),eid,rid))
    return {'ok':True}
@app.delete('/api/events/{eid}/rooms/{rid}')
def event_room_delete(eid:int,rid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('DELETE FROM event_rooms WHERE event_id=? AND room_id=?',(eid,rid))
    return {'ok':True}

@app.post('/api/operators')
def operator_create(x:OperatorIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a);n=x.name.strip()
    if not n:raise HTTPException(400,'Name required')
    with db() as c:
        r=c.execute('SELECT id FROM operators WHERE lower(name)=lower(?)',(n,)).fetchone()
        if r:c.execute('UPDATE operators SET active=1,name=? WHERE id=?',(n,r['id']));oid=r['id']
        else:oid=c.execute('INSERT INTO operators(name) VALUES(?)',(n,)).lastrowid
    return {'id':oid}
@app.delete('/api/operators/{oid}')
def operator_delete(oid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE operators SET active=0 WHERE id=?',(oid,))
    return {'ok':True}

@app.get('/api/accounts')
def account_list(authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_admin(a)
    with db() as c:return [dict(r) for r in c.execute('SELECT id,username,display_name,role,active FROM accounts ORDER BY username')]
@app.post('/api/accounts')
def account_create(x:AccountIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_admin(a)
    if x.role not in ('admin','speaker_preview'):raise HTTPException(400,'Invalid role')
    if len(x.password)<8:raise HTTPException(400,'Password must be at least 8 characters')
    with db() as c:
        try:aid=c.execute('INSERT INTO accounts(username,password_hash,display_name,role,active) VALUES(?,?,?,?,1)',(x.username.strip(),pw_hash(x.password),x.display_name.strip(),x.role)).lastrowid
        except sqlite3.IntegrityError:raise HTTPException(409,'Username already exists')
    return {'id':aid}
@app.patch('/api/accounts/{aid}/password')
def account_password(aid:int,x:PasswordIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_admin(a)
    if len(x.password)<8:raise HTTPException(400,'Password must be at least 8 characters')
    with db() as c:c.execute('UPDATE accounts SET password_hash=? WHERE id=?',(pw_hash(x.password),aid));c.execute('DELETE FROM sessions WHERE account_id=?',(aid,))
    return {'ok':True}
@app.delete('/api/accounts/{aid}')
def account_disable(aid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_admin(a)
    if aid==a['id']:raise HTTPException(400,'Cannot disable your own account')
    with db() as c:c.execute('UPDATE accounts SET active=0 WHERE id=?',(aid,));c.execute('DELETE FROM sessions WHERE account_id=?',(aid,))
    return {'ok':True}

@app.patch('/api/settings')
def settings_update(p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_admin(a);allowed={'venue_name','control_centre_name','attachment_limit_mb'}
    with db() as c:
        for k,v in p.items():
            if k in allowed:c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
    return {'ok':True}

@app.get('/api/messages')
def messages(scope:str,scope_id:int|None=None,authorization:str|None=Header(default=None)):
    require_auth(authorization)
    with db() as c:
        rows=c.execute("SELECT * FROM messages WHERE scope='venue' ORDER BY id DESC LIMIT 250") if scope=='venue' else c.execute('SELECT * FROM messages WHERE scope=? AND scope_id=? ORDER BY id DESC LIMIT 250',(scope,scope_id));out=[]
        for r in reversed(rows.fetchall()):
            d=dict(r);d['attachments']=[dict(x) for x in c.execute('SELECT * FROM attachments WHERE message_id=?',(r['id'],))];out.append(d)
        return out
@app.post('/api/messages')
def message_create(x:MessageIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);sender=x.sender.strip() or a['display_name']
    with db() as c:mid=c.execute('INSERT INTO messages(scope,scope_id,sender,body,priority,created_at) VALUES(?,?,?,?,?,?)',(x.scope,x.scope_id,sender,x.body,x.priority,now())).lastrowid
    return {'id':mid}
@app.post('/api/messages/{mid}/attachments')
async def attachment_add(mid:int,file:UploadFile=File(...),authorization:str|None=Header(default=None)):
    require_auth(authorization)
    with db() as c:lim=int(setting(c,'attachment_limit_mb','25'))
    safe=''.join(ch for ch in (file.filename or 'file') if ch.isalnum() or ch in '._- ')[:180] or 'file';stored=uuid.uuid4().hex+'_'+safe;dest=UP/stored;size=0
    with dest.open('wb') as f:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            if size>lim*1024*1024:f.close();dest.unlink(missing_ok=True);raise HTTPException(413,f'{lim}MB limit')
            f.write(chunk)
    with db() as c:c.execute('INSERT INTO attachments(message_id,original_name,stored_name,mime_type,size) VALUES(?,?,?,?,?)',(mid,file.filename or safe,stored,file.content_type or '',size))
    return {'ok':True}
@app.get('/api/attachments/{aid}')
def attachment_get(aid:int,authorization:str|None=Header(default=None)):
    require_auth(authorization)
    with db() as c:r=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
    if not r:raise HTTPException(404)
    return FileResponse(UP/r['stored_name'],media_type=r['mime_type'] or 'application/octet-stream',filename=r['original_name'])

@app.post('/api/help')
def help_create(x:HelpIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization)
    with db() as c:
        rr=c.execute('SELECT name FROM rooms WHERE id=?',(x.room_id,)).fetchone() if x.room_id else None
        hid=c.execute("INSERT INTO help_requests(event_id,room_id,room_name,requested_by,category,description,priority,status,created_at) VALUES(?,?,?,?,?,?,?,'new',?)",(x.event_id,x.room_id,rr['name'] if rr else '',x.requested_by or a['display_name'],x.category,x.description,x.priority,now())).lastrowid
    return {'id':hid}
@app.patch('/api/help/{hid}')
def help_update(hid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a);st=p.get('status')
    with db() as c:
        if st=='acknowledged':c.execute('UPDATE help_requests SET status=?,acknowledged_at=? WHERE id=?',(st,now(),hid))
        elif st=='resolved':c.execute('UPDATE help_requests SET status=?,resolved_at=? WHERE id=?',(st,now(),hid))
        elif st:c.execute('UPDATE help_requests SET status=? WHERE id=?',(st,hid))
        if 'assigned_to' in p:c.execute('UPDATE help_requests SET assigned_to=? WHERE id=?',(p.get('assigned_to',''),hid))
    return {'ok':True}

@app.post('/api/devices/register')
def device_register(x:DeviceIn):
    # Client device registration remains local-network friendly and does not require a Control Centre login.
    with db() as c:c.execute("INSERT INTO devices(name,role,room_id,event_id,operator,online_status,last_heartbeat,app_version) VALUES(?,?,?,?,?,'online',?,?) ON CONFLICT(name) DO UPDATE SET role=excluded.role,room_id=excluded.room_id,event_id=excluded.event_id,operator=excluded.operator,online_status='online',last_heartbeat=excluded.last_heartbeat,app_version=excluded.app_version",(x.name,x.role,x.room_id,x.event_id,x.operator,now(),x.app_version))
    return {'ok':True}
@app.post('/api/devices/heartbeat')
def device_heartbeat(p:dict):
    with db() as c:c.execute("UPDATE devices SET online_status='online',last_heartbeat=? WHERE name=?",(now(),p.get('name','')))
    return {'ok':True}

@app.websocket('/ws')
async def websocket(w:WebSocket):
    await w.accept()
    try:
        while True:await w.receive_text()
    except WebSocketDisconnect:pass
