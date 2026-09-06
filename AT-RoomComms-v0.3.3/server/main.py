import os, sqlite3, hashlib, hmac, secrets, uuid, json, asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

VERSION='0.5.0'
DATA=Path(os.getenv('ROOMCOMMS_DATA','/data')); DB=DATA/'roomcomms.db'; UP=DATA/'uploads'
DATA.mkdir(parents=True,exist_ok=True); UP.mkdir(exist_ok=True)
app=FastAPI(title='AT RoomComms',version=VERSION)
app.mount('/static',StaticFiles(directory=Path(__file__).parent/'static'),name='static')

def now(): return datetime.now(timezone.utc).isoformat()

class ConnectionManager:
    def __init__(self):self.conns={}
    async def connect(self,ws,actor):await ws.accept();self.conns[ws]=actor
    def disconnect(self,ws):self.conns.pop(ws,None)
    async def broadcast(self,payload,visible=None):
        dead=[]
        for ws,actor in list(self.conns.items()):
            if visible and not visible(actor):continue
            try:await ws.send_text(json.dumps(payload))
            except Exception:dead.append(ws)
        for ws in dead:self.conns.pop(ws,None)
manager=ConnectionManager()

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

def last_cutoff(hhmm):
    try: h,m=[int(x) for x in hhmm.split(':',1)]
    except Exception: h,m=3,0
    n=datetime.now(timezone.utc)
    candidate=n.replace(hour=h,minute=m,second=0,microsecond=0)
    if candidate>n:candidate-=timedelta(days=1)
    return candidate
def next_cutoff(hhmm):
    return last_cutoff(hhmm)+timedelta(days=1)
def is_expired(created_at_iso,cutoff_dt):
    try:return datetime.fromisoformat(created_at_iso)<cutoff_dt
    except Exception:return False

def init():
    with db() as c:
        c.executescript('''
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,display_name TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,account_id INTEGER NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS operators(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS operator_sessions(token TEXT PRIMARY KEY,operator_id INTEGER NOT NULL,event_id INTEGER,room_id INTEGER,device_role TEXT DEFAULT 'main',device_name TEXT DEFAULT '',created_at TEXT NOT NULL,FOREIGN KEY(operator_id) REFERENCES operators(id) ON DELETE CASCADE);
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
        mcols=[r['name'] for r in c.execute('PRAGMA table_info(messages)')]
        if 'sender_id' not in mcols:c.execute('ALTER TABLE messages ADD COLUMN sender_id INTEGER')
        if 'edited_at' not in mcols:c.execute('ALTER TABLE messages ADD COLUMN edited_at TEXT')
        if 'deleted_at' not in mcols:c.execute('ALTER TABLE messages ADD COLUMN deleted_at TEXT')
        if 'sender_kind' not in mcols:c.execute("ALTER TABLE messages ADD COLUMN sender_kind TEXT DEFAULT 'account'")
        if 'to_kind' not in mcols:c.execute('ALTER TABLE messages ADD COLUMN to_kind TEXT')
        if 'to_id' not in mcols:c.execute('ALTER TABLE messages ADD COLUMN to_id INTEGER')
        if 'help_request_id' not in mcols:c.execute('ALTER TABLE messages ADD COLUMN help_request_id INTEGER')
        hcols=[r['name'] for r in c.execute('PRAGMA table_info(help_requests)')]
        if 'broadcast' not in hcols:c.execute('ALTER TABLE help_requests ADD COLUMN broadcast INTEGER DEFAULT 0')
        if 'scope' not in hcols:
            c.execute("ALTER TABLE help_requests ADD COLUMN scope TEXT DEFAULT 'room'")
            c.execute("UPDATE help_requests SET scope='venue' WHERE broadcast=1")
        rcols=[r['name'] for r in c.execute('PRAGMA table_info(rooms)')]
        if 'event_id' not in rcols:
            c.execute('ALTER TABLE rooms ADD COLUMN event_id INTEGER')
            c.execute('ALTER TABLE rooms ADD COLUMN operator_name TEXT DEFAULT \'\'')
            # Rooms used to be a shared library assigned to events via event_rooms.
            # Fold that into a direct one-event ownership: each room now belongs to
            # whichever event it was (most recently) assigned to.
            for row in c.execute('SELECT room_id,event_id,operator_name FROM event_rooms er WHERE er.event_id=(SELECT MAX(event_id) FROM event_rooms WHERE room_id=er.room_id)'):
                c.execute('UPDATE rooms SET event_id=?,operator_name=? WHERE id=?',(row['event_id'],row['operator_name'] or '',row['room_id']))
        c.execute("INSERT OR IGNORE INTO settings VALUES('venue_name','Harrogate Convention Centre')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('control_centre_name','Speaker Preview')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('attachment_limit_mb','25')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('daily_logoff_utc','03:00')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('ui_theme','blue')")
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
class RoomIn(BaseModel): name:str; short_name:str=''; current_status:str='closed'; event_id:int|None=None; operator_name:str=''
class OperatorIn(BaseModel): name:str
class AccountIn(BaseModel): username:str; password:str; display_name:str; role:str='speaker_preview'
class PasswordIn(BaseModel): password:str
class MessageIn(BaseModel): scope:str; scope_id:int|None=None; body:str=''; priority:str='normal'
class MessageEdit(BaseModel): body:str
class DeviceIn(BaseModel): name:str; role:str='general'; room_id:int|None=None; event_id:int|None=None; operator:str=''; app_version:str=''
class HelpIn(BaseModel): event_id:int|None=None; room_id:int|None=None; requested_by:str=''; category:str; description:str; priority:str='important'; scope:str='room'
class OperatorLoginIn(BaseModel): operator_id:int; event_id:int; room_id:int; device_role:str='main'; device_name:str=''
class DMIn(BaseModel): to_kind:str; to_id:int; body:str

def account_for_token(token:str):
    with db() as c:
        r=c.execute('SELECT a.id,a.username,a.display_name,a.role,a.active,s.created_at FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token=?',(token,)).fetchone()
        if not r or not r['active']:return None
        cutoff=last_cutoff(setting(c,'daily_logoff_utc','03:00'))
        if is_expired(r['created_at'],cutoff):
            c.execute('DELETE FROM sessions WHERE token=?',(token,))
            return None
    d=dict(r);d.pop('created_at',None);d['kind']='account';d['room_id']=None;d['event_id']=None;d['device_role']=None
    return d

def operator_for_token(token:str):
    with db() as c:
        r=c.execute('SELECT os.operator_id,os.event_id,os.room_id,os.device_role,os.device_name,os.created_at,o.name,o.active FROM operator_sessions os JOIN operators o ON o.id=os.operator_id WHERE os.token=?',(token,)).fetchone()
        if not r or not r['active']:return None
        cutoff=last_cutoff(setting(c,'daily_logoff_utc','03:00'))
        if is_expired(r['created_at'],cutoff):
            c.execute('DELETE FROM operator_sessions WHERE token=?',(token,))
            return None
    return {'kind':'operator','id':r['operator_id'],'username':None,'display_name':r['name'],'role':None,'active':1,'room_id':r['room_id'],'event_id':r['event_id'],'device_role':r['device_role'],'device_name':r['device_name']}

def actor_for_token(token:str):
    return account_for_token(token) or operator_for_token(token)

def require_auth(authorization:str|None):
    if not setup_complete():raise HTTPException(503,'First run setup required')
    if not authorization or not authorization.lower().startswith('bearer '):raise HTTPException(401,'Login required')
    token=authorization.split(' ',1)[1].strip()
    a=account_for_token(token)
    if not a:raise HTTPException(401,'Session invalid')
    return a
def require_actor(authorization:str|None):
    if not setup_complete():raise HTTPException(503,'First run setup required')
    if not authorization or not authorization.lower().startswith('bearer '):raise HTTPException(401,'Login required')
    token=authorization.split(' ',1)[1].strip()
    a=actor_for_token(token)
    if not a:raise HTTPException(401,'Session invalid')
    return a
def require_manager(a):
    if a['role'] not in ('admin','speaker_preview'):raise HTTPException(403,'Manager permission required')
def require_admin(a):
    if a['role']!='admin':raise HTTPException(403,'Administrator permission required')

def actor_can_access(actor,c,scope,scope_id):
    if actor['kind']=='account':return True
    if scope=='room':return scope_id==actor['room_id']
    if scope=='emergency_thread':
        orig=c.execute('SELECT sender_kind,sender_id FROM messages WHERE id=?',(scope_id,)).fetchone()
        return bool(orig) and orig['sender_kind']=='operator' and orig['sender_id']==actor['id']
    if scope=='help_thread':
        hr=c.execute('SELECT room_id,event_id,scope FROM help_requests WHERE id=?',(scope_id,)).fetchone()
        return bool(hr) and (hr['room_id']==actor['room_id'] or hr['scope']=='venue' or (hr['scope']=='event' and hr['event_id']==actor['event_id']))
    return False
def message_access_ok(actor,c,m):
    if m['scope']=='dm':
        return (m['sender_kind'],m['sender_id'])==(actor['kind'],actor['id']) or (m['to_kind'],m['to_id'])==(actor['kind'],actor['id'])
    return actor_can_access(actor,c,m['scope'],m['scope_id'])
def broadcast_extras(c,scope,scope_id):
    thread_owner=None;help_room_id=None;help_event_id=None;help_scope='room'
    if scope=='emergency_thread':
        orig=c.execute('SELECT sender_kind,sender_id FROM messages WHERE id=?',(scope_id,)).fetchone()
        if orig:thread_owner=(orig['sender_kind'],orig['sender_id'])
    elif scope=='help_thread':
        hr=c.execute('SELECT room_id,event_id,scope FROM help_requests WHERE id=?',(scope_id,)).fetchone()
        if hr:help_room_id=hr['room_id'];help_event_id=hr['event_id'];help_scope=hr['scope'] or 'room'
    return thread_owner,help_room_id,help_event_id,help_scope
def visible_predicate(scope,scope_id,thread_owner=None,help_room_id=None,help_event_id=None,help_scope='room',priority=None):
    if scope=='room':
        if priority=='emergency':return lambda actor:True
        return lambda actor:actor['kind']=='account' or (actor['kind']=='operator' and actor['room_id']==scope_id)
    if scope=='emergency_thread':
        return lambda actor:actor['kind']=='account' or (actor['kind']=='operator' and thread_owner==(actor['kind'],actor['id']))
    if scope=='help_thread':
        if help_scope=='venue':return lambda actor:True
        if help_scope=='event':return lambda actor:actor['kind']=='account' or (actor['kind']=='operator' and actor['event_id']==help_event_id)
        return lambda actor:actor['kind']=='account' or (actor['kind']=='operator' and actor['room_id']==help_room_id)
    return lambda actor:actor['kind']=='account'

@app.get('/',response_class=HTMLResponse)
def home():
    html=(Path(__file__).parent/'static'/'index.html').read_text(encoding='utf-8')
    html=html.replace('app.css"','app.css?v='+VERSION+'"').replace('app.js"','app.js?v='+VERSION+'"')
    return HTMLResponse(html)
@app.get('/api/health')
def health():return {'status':'ok','version':VERSION}
@app.get('/api/setup/status')
def setup_status():
    with db() as c:theme=setting(c,'ui_theme','blue')
    return {'needs_setup':not setup_complete(),'version':VERSION,'theme':theme}
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
def me(authorization:str|None=Header(default=None)):return require_actor(authorization)

@app.get('/api/operator/login-options')
def operator_login_options():
    if not setup_complete():raise HTTPException(503,'First run setup required')
    with db() as c:
        operators=[dict(r) for r in c.execute('SELECT id,name FROM operators WHERE active=1 ORDER BY name')]
        events=[]
        for e in c.execute('SELECT * FROM events WHERE archived=0 ORDER BY starts_at,name'):
            rooms=[dict(r) for r in c.execute('SELECT id,name,short_name FROM rooms WHERE event_id=? AND enabled=1 ORDER BY name',(e['id'],))]
            events.append({**dict(e),'rooms':rooms})
    return {'operators':operators,'events':events}
@app.post('/api/operator/login')
def operator_login(x:OperatorLoginIn):
    if not setup_complete():raise HTTPException(503,'First run setup required')
    if x.device_role not in ('main','backup'):raise HTTPException(400,'Invalid device role')
    with db() as c:
        op=c.execute('SELECT * FROM operators WHERE id=? AND active=1',(x.operator_id,)).fetchone()
        if not op:raise HTTPException(404,'Operator not found')
        if not c.execute('SELECT 1 FROM events WHERE id=? AND archived=0',(x.event_id,)).fetchone():raise HTTPException(404,'Event not found')
        if not c.execute('SELECT 1 FROM rooms WHERE id=? AND enabled=1 AND event_id=?',(x.room_id,x.event_id)).fetchone():raise HTTPException(400,'That room is not part of that event')
        token=secrets.token_urlsafe(32)
        c.execute('INSERT INTO operator_sessions(token,operator_id,event_id,room_id,device_role,device_name,created_at) VALUES(?,?,?,?,?,?,?)',(token,op['id'],x.event_id,x.room_id,x.device_role,x.device_name.strip(),now()))
    return {'token':token,'user':{'id':op['id'],'display_name':op['name'],'kind':'operator','room_id':x.room_id,'event_id':x.event_id,'device_role':x.device_role}}
@app.post('/api/operator/logout')
def operator_logout(authorization:str|None=Header(default=None)):
    if authorization and authorization.lower().startswith('bearer '):
        with db() as c:c.execute('DELETE FROM operator_sessions WHERE token=?',(authorization.split(' ',1)[1].strip(),))
    return {'ok':True}

@app.get('/api/bootstrap')
def bootstrap(authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    with db() as c:
        if a['kind']=='operator':
            room=c.execute('SELECT * FROM rooms WHERE id=?',(a['room_id'],)).fetchone()
            event=c.execute('SELECT * FROM events WHERE id=?',(a['event_id'],)).fetchone()
            help_requests=[dict(r) for r in c.execute("SELECT * FROM help_requests WHERE (room_id=? OR scope='venue' OR (scope='event' AND event_id=?)) AND status NOT IN ('resolved','cancelled') ORDER BY id DESC",(a['room_id'],a['event_id']))]
            return {'version':VERSION,'me':a,'settings':{'venue_name':setting(c,'venue_name'),'control_centre_name':setting(c,'control_centre_name'),'ui_theme':setting(c,'ui_theme','blue')},'room':dict(room) if room else None,'event':dict(event) if event else None,'help_requests':help_requests}
        return {'version':VERSION,'me':a,'settings':{r['key']:r['value'] for r in c.execute('SELECT * FROM settings')},'rooms':[dict(r) for r in c.execute('SELECT * FROM rooms WHERE enabled=1 ORDER BY event_id,name')],'events':[dict(r) for r in c.execute('SELECT * FROM events WHERE archived=0 ORDER BY starts_at,name')],'operators':[dict(r) for r in c.execute('SELECT * FROM operators WHERE active=1 ORDER BY name')],'devices':[dict(r) for r in c.execute('SELECT * FROM devices ORDER BY name')],'help_requests':[dict(r) for r in c.execute("SELECT * FROM help_requests WHERE status NOT IN ('resolved','cancelled') ORDER BY id DESC")]}

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
    with db() as c:
        c.execute('UPDATE rooms SET enabled=0 WHERE event_id=?',(eid,))
        c.execute('DELETE FROM event_rooms WHERE event_id=?',(eid,))
        c.execute('DELETE FROM events WHERE id=?',(eid,))
    return {'ok':True}

@app.post('/api/rooms')
def room_create(x:RoomIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    if not x.event_id:raise HTTPException(400,'A room must belong to an event')
    with db() as c:
        if not c.execute('SELECT 1 FROM events WHERE id=? AND archived=0',(x.event_id,)).fetchone():raise HTTPException(404,'Event not found')
        try:rid=c.execute('INSERT INTO rooms(name,short_name,current_status,event_id,operator_name) VALUES(?,?,?,?,?)',(x.name.strip(),x.short_name.strip(),x.current_status,x.event_id,x.operator_name.strip())).lastrowid
        except sqlite3.IntegrityError:raise HTTPException(409,'Room already exists')
    return {'id':rid}
@app.patch('/api/rooms/{rid}')
def room_update(rid:int,x:RoomIn,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE rooms SET name=?,short_name=?,current_status=?,operator_name=? WHERE id=?',(x.name.strip(),x.short_name.strip(),x.current_status,x.operator_name.strip(),rid))
    return {'ok':True}
@app.delete('/api/rooms/{rid}')
def room_delete(rid:int,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE rooms SET enabled=0 WHERE id=?',(rid,))
    return {'ok':True}
@app.patch('/api/rooms/{rid}/status')
def room_status(rid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a)
    with db() as c:c.execute('UPDATE rooms SET current_status=? WHERE id=?',(p.get('status','closed'),rid))
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
    with db() as c:c.execute('UPDATE operators SET active=0 WHERE id=?',(oid,));c.execute('DELETE FROM operator_sessions WHERE operator_id=?',(oid,))
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
    a=require_auth(authorization);require_admin(a);allowed={'venue_name','control_centre_name','daily_logoff_utc','ui_theme'}
    if 'ui_theme' in p and p['ui_theme'] not in ('blue','purple','green','orange'):raise HTTPException(400,'Invalid theme')
    with db() as c:
        for k,v in p.items():
            if k in allowed:c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
    return {'ok':True}

def message_dict(c,mid):
    r=c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone()
    if not r:return None
    d=dict(r);d['attachments']=[dict(x) for x in c.execute('SELECT * FROM attachments WHERE message_id=?',(mid,))]
    return d

@app.get('/api/messages')
def messages(scope:str,scope_id:int|None=None,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    with db() as c:
        if not actor_can_access(a,c,scope,scope_id):raise HTTPException(403,'No access to this feed')
        rows=c.execute("SELECT * FROM messages WHERE scope='venue' AND deleted_at IS NULL ORDER BY id DESC LIMIT 250") if scope=='venue' else c.execute('SELECT * FROM messages WHERE scope=? AND scope_id=? AND deleted_at IS NULL ORDER BY id DESC LIMIT 250',(scope,scope_id));out=[]
        for r in reversed(rows.fetchall()):
            d=dict(r);d['attachments']=[dict(x) for x in c.execute('SELECT * FROM attachments WHERE message_id=?',(r['id'],))];out.append(d)
        return out
@app.post('/api/messages')
async def message_create(x:MessageIn,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    if x.scope not in ('venue','event','room','emergency_thread','help_thread'):raise HTTPException(400,'Invalid scope')
    body=x.body.strip()
    if not body:raise HTTPException(400,'Message cannot be empty')
    with db() as c:
        if not actor_can_access(a,c,x.scope,x.scope_id):raise HTTPException(403,'No access to this feed')
        thread_owner=None;help_room_id=None;help_event_id=None;help_scope='room'
        if x.scope=='emergency_thread':
            orig=c.execute('SELECT sender_kind,sender_id FROM messages WHERE id=?',(x.scope_id,)).fetchone()
            if not orig:raise HTTPException(404,'Original message not found')
            thread_owner=(orig['sender_kind'],orig['sender_id'])
        if x.scope=='help_thread':
            hr=c.execute('SELECT room_id,event_id,scope FROM help_requests WHERE id=?',(x.scope_id,)).fetchone()
            if not hr:raise HTTPException(404,'Help request not found')
            help_room_id=hr['room_id'];help_event_id=hr['event_id'];help_scope=hr['scope'] or 'room'
        mid=c.execute('INSERT INTO messages(scope,scope_id,sender,sender_id,sender_kind,body,priority,created_at) VALUES(?,?,?,?,?,?,?,?)',(x.scope,x.scope_id,a['display_name'],a['id'],a['kind'],body,x.priority,now())).lastrowid
        d=message_dict(c,mid)
        emg_room_name=emg_event_name=None
        if x.scope=='room' and x.priority=='emergency':
            room=c.execute('SELECT name,event_id FROM rooms WHERE id=?',(x.scope_id,)).fetchone()
            if room:
                emg_room_name=room['name']
                ev=c.execute('SELECT name FROM events WHERE id=?',(room['event_id'],)).fetchone()
                emg_event_name=ev['name'] if ev else ''
    await manager.broadcast({'type':'message_new','message':d},visible=visible_predicate(x.scope,x.scope_id,thread_owner=thread_owner,help_room_id=help_room_id,help_event_id=help_event_id,help_scope=help_scope,priority=x.priority))
    if emg_room_name is not None:
        await manager.broadcast({'type':'emergency_alert','room_id':x.scope_id,'room_name':emg_room_name,'event_name':emg_event_name,'body':body,'sender':a['display_name'],'sender_kind':a['kind'],'sender_id':a['id'],'message_id':mid})
    return d
@app.patch('/api/messages/{mid}')
async def message_edit(mid:int,x:MessageEdit,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    with db() as c:
        m=c.execute('SELECT * FROM messages WHERE id=? AND deleted_at IS NULL',(mid,)).fetchone()
        if not m:raise HTTPException(404,'Message not found')
        is_owner=m['sender_kind']==a['kind'] and m['sender_id']==a['id']
        is_admin_override=a['kind']=='account' and a['role']=='admin'
        if not (is_owner or is_admin_override):raise HTTPException(403,'You can only edit your own messages')
        body=x.body.strip()
        if not body:raise HTTPException(400,'Message cannot be empty')
        c.execute('UPDATE messages SET body=?,edited_at=? WHERE id=?',(body,now(),mid))
        d=message_dict(c,mid)
        thread_owner,help_room_id,help_event_id,help_scope=broadcast_extras(c,m['scope'],m['scope_id'])
    await manager.broadcast({'type':'message_updated','message':d},visible=visible_predicate(m['scope'],m['scope_id'],thread_owner=thread_owner,help_room_id=help_room_id,help_event_id=help_event_id,help_scope=help_scope,priority=m['priority']))
    return d
@app.delete('/api/messages/{mid}')
async def message_delete(mid:int,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    with db() as c:
        m=c.execute('SELECT * FROM messages WHERE id=? AND deleted_at IS NULL',(mid,)).fetchone()
        if not m:raise HTTPException(404,'Message not found')
        is_owner=m['sender_kind']==a['kind'] and m['sender_id']==a['id']
        is_admin_override=a['kind']=='account' and a['role']=='admin'
        if not (is_owner or is_admin_override):raise HTTPException(403,'You can only delete your own messages')
        c.execute('UPDATE messages SET deleted_at=? WHERE id=?',(now(),mid))
        scope,scope_id=m['scope'],m['scope_id']
        thread_owner,help_room_id,help_event_id,help_scope=broadcast_extras(c,scope,scope_id)
    await manager.broadcast({'type':'message_deleted','id':mid,'scope':scope,'scope_id':scope_id},visible=visible_predicate(scope,scope_id,thread_owner=thread_owner,help_room_id=help_room_id,help_event_id=help_event_id,help_scope=help_scope,priority=m['priority']))
    return {'ok':True}
@app.post('/api/messages/{mid}/attachments')
async def attachment_add(mid:int,file:UploadFile=File(...),authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    with db() as c:
        m=c.execute('SELECT * FROM messages WHERE id=? AND deleted_at IS NULL',(mid,)).fetchone()
        if not m:raise HTTPException(404,'Message not found')
        if not message_access_ok(a,c,m):raise HTTPException(403,'No access to this feed')
    safe=''.join(ch for ch in (file.filename or 'file') if ch.isalnum() or ch in '._- ')[:180] or 'file';stored=uuid.uuid4().hex+'_'+safe;dest=UP/stored;size=0
    with dest.open('wb') as f:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            f.write(chunk)
    with db() as c:
        c.execute('INSERT INTO attachments(message_id,original_name,stored_name,mime_type,size) VALUES(?,?,?,?,?)',(mid,file.filename or safe,stored,file.content_type or '',size))
        d=message_dict(c,mid)
        thread_owner,help_room_id,help_event_id,help_scope=broadcast_extras(c,m['scope'],m['scope_id'])
    if d:
        if m['scope']=='dm':
            pair={(m['sender_kind'],m['sender_id']),(m['to_kind'],m['to_id'])}
            await manager.broadcast({'type':'message_updated','message':d},visible=lambda actor:(actor['kind'],actor['id']) in pair)
        else:
            await manager.broadcast({'type':'message_updated','message':d},visible=visible_predicate(m['scope'],m['scope_id'],thread_owner=thread_owner,help_room_id=help_room_id,help_event_id=help_event_id,help_scope=help_scope,priority=m['priority']))
    return d or {'ok':True}
@app.get('/api/attachments/{aid}')
def attachment_get(aid:int,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    with db() as c:
        r=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
        if not r:raise HTTPException(404)
        m=c.execute('SELECT * FROM messages WHERE id=?',(r['message_id'],)).fetchone()
        if not m or not message_access_ok(a,c,m):raise HTTPException(403)
    return FileResponse(UP/r['stored_name'],media_type=r['mime_type'] or 'application/octet-stream',filename=r['original_name'])

@app.get('/api/dm/contacts')
def dm_contacts(authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    with db() as c:
        accts=c.execute('SELECT id,display_name FROM accounts WHERE active=1').fetchall()
        out=[{'kind':'account','id':r['id'],'display_name':r['display_name']} for r in accts if not (a['kind']=='account' and r['id']==a['id'])]
        if a['kind']=='account':
            out+=[{'kind':'operator','id':r['id'],'display_name':r['name']} for r in c.execute('SELECT id,name FROM operators WHERE active=1')]
    return out
@app.get('/api/dm')
def dm_thread(with_kind:str,with_id:int,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    if a['kind']=='operator' and with_kind!='account':raise HTTPException(403,'Operators can only message Control Centre accounts')
    with db() as c:
        rows=c.execute("SELECT * FROM messages WHERE scope='dm' AND deleted_at IS NULL AND ((sender_kind=? AND sender_id=? AND to_kind=? AND to_id=?) OR (sender_kind=? AND sender_id=? AND to_kind=? AND to_id=?)) ORDER BY id DESC LIMIT 250",(a['kind'],a['id'],with_kind,with_id,with_kind,with_id,a['kind'],a['id']))
        out=[]
        for r in reversed(rows.fetchall()):
            d=dict(r);d['attachments']=[dict(x) for x in c.execute('SELECT * FROM attachments WHERE message_id=?',(r['id'],))];out.append(d)
    return out
@app.post('/api/dm')
async def dm_send(x:DMIn,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    if x.to_kind not in ('account','operator'):raise HTTPException(400,'Invalid recipient')
    if a['kind']=='operator' and x.to_kind!='account':raise HTTPException(403,'Operators can only message Control Centre accounts')
    body=x.body.strip()
    if not body:raise HTTPException(400,'Message cannot be empty')
    with db() as c:
        if x.to_kind=='account':t=c.execute('SELECT id FROM accounts WHERE id=? AND active=1',(x.to_id,)).fetchone()
        else:t=c.execute('SELECT id FROM operators WHERE id=? AND active=1',(x.to_id,)).fetchone()
        if not t:raise HTTPException(404,'Recipient not found')
        mid=c.execute('INSERT INTO messages(scope,scope_id,sender,sender_id,sender_kind,body,priority,created_at,to_kind,to_id) VALUES(?,?,?,?,?,?,?,?,?,?)',('dm',None,a['display_name'],a['id'],a['kind'],body,'normal',now(),x.to_kind,x.to_id)).lastrowid
        d=message_dict(c,mid)
    pair={(a['kind'],a['id']),(x.to_kind,x.to_id)}
    await manager.broadcast({'type':'dm_new','message':d},visible=lambda actor:(actor['kind'],actor['id']) in pair)
    return d

def help_visible(room_id,event_id,scope):
    if scope=='venue':return None
    if scope=='event':return lambda actor:actor['kind']=='account' or actor['event_id']==event_id
    return lambda actor:actor['kind']=='account' or actor['room_id']==room_id
@app.post('/api/help')
async def help_create(x:HelpIn,authorization:str|None=Header(default=None)):
    a=require_actor(authorization)
    event_id,room_id=x.event_id,x.room_id
    if a['kind']=='operator':event_id,room_id=a['event_id'],a['room_id']
    if not room_id:raise HTTPException(400,'A room is required for a help request')
    scope=x.scope if x.scope in ('room','event','venue') else 'room'
    with db() as c:
        rr=c.execute('SELECT name FROM rooms WHERE id=?',(room_id,)).fetchone()
        room_name=rr['name'] if rr else ''
        hid=c.execute("INSERT INTO help_requests(event_id,room_id,room_name,requested_by,category,description,priority,status,created_at,broadcast,scope) VALUES(?,?,?,?,?,?,?,'new',?,?,?)",(event_id,room_id,room_name,x.requested_by.strip() or a['display_name'],x.category,x.description,x.priority,now(),1 if scope=='venue' else 0,scope)).lastrowid
        hr=dict(c.execute('SELECT * FROM help_requests WHERE id=?',(hid,)).fetchone())
        tag={'room':'🆘 Help requested — ','event':'📣 Event-wide help — ','venue':'📢 All-call — '}[scope]
        feed_body=tag+f"{x.category}: {x.description}"+(f' ({room_name})' if scope!='room' else '')
        mid=c.execute('INSERT INTO messages(scope,scope_id,sender,sender_id,sender_kind,body,priority,created_at,help_request_id) VALUES(?,?,?,?,?,?,?,?,?)',('room',room_id,a['display_name'],a['id'],a['kind'],feed_body,'urgent',now(),hid)).lastrowid
        msg=message_dict(c,mid)
    await manager.broadcast({'type':'help_new','request':hr},visible=help_visible(room_id,event_id,scope))
    await manager.broadcast({'type':'message_new','message':msg},visible=help_visible(room_id,event_id,scope))
    return {'id':hid}
@app.get('/api/help')
def help_list(authorization:str|None=Header(default=None)):
    require_auth(authorization)
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM help_requests ORDER BY id DESC LIMIT 250')]
@app.patch('/api/help/{hid}')
async def help_update(hid:int,p:dict,authorization:str|None=Header(default=None)):
    a=require_auth(authorization);require_manager(a);st=p.get('status')
    with db() as c:
        if st=='acknowledged':c.execute('UPDATE help_requests SET status=?,acknowledged_at=? WHERE id=?',(st,now(),hid))
        elif st=='resolved':c.execute('UPDATE help_requests SET status=?,resolved_at=? WHERE id=?',(st,now(),hid))
        elif st:c.execute('UPDATE help_requests SET status=? WHERE id=?',(st,hid))
        if 'assigned_to' in p:c.execute('UPDATE help_requests SET assigned_to=? WHERE id=?',(p.get('assigned_to',''),hid))
        hr=dict(c.execute('SELECT * FROM help_requests WHERE id=?',(hid,)).fetchone())
    await manager.broadcast({'type':'help_updated','request':hr},visible=help_visible(hr['room_id'],hr['event_id'],hr['scope'] or 'room'))
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
    token=w.query_params.get('token','')
    if not setup_complete():
        await w.close(code=4401);return
    actor=actor_for_token(token)
    if not actor:
        await w.close(code=4401);return
    await manager.connect(w,actor)
    try:
        while True:await w.receive_text()
    except WebSocketDisconnect:pass
    finally:manager.disconnect(w)

async def cutoff_sweeper():
    while True:
        with db() as c:hhmm=setting(c,'daily_logoff_utc','03:00')
        delay=max(1,(next_cutoff(hhmm)-datetime.now(timezone.utc)).total_seconds())
        await asyncio.sleep(delay)
        with db() as c:
            c.execute('DELETE FROM sessions')
            c.execute('DELETE FROM operator_sessions')
        await manager.broadcast({'type':'force_logout'})
@app.on_event('startup')
async def _on_startup():
    asyncio.create_task(cutoff_sweeper())
