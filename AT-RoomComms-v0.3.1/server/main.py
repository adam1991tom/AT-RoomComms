import os, sqlite3, uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
VERSION='0.3.1'; DATA=Path(os.getenv('ROOMCOMMS_DATA','/data')); DB=DATA/'roomcomms.db'; UP=DATA/'uploads'; DATA.mkdir(parents=True,exist_ok=True); UP.mkdir(exist_ok=True)
app=FastAPI(title='AT RoomComms',version=VERSION); app.mount('/static',StaticFiles(directory=Path(__file__).parent/'static'),name='static')
def now(): return datetime.now(timezone.utc).isoformat()
def db(): c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY,name TEXT UNIQUE,short_name TEXT,current_status TEXT DEFAULT 'closed',enabled INTEGER DEFAULT 1); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,name TEXT,client TEXT,event_color TEXT,starts_at TEXT,ends_at TEXT,event_status TEXT DEFAULT 'scheduled',archived INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS event_rooms(event_id INTEGER,room_id INTEGER,PRIMARY KEY(event_id,room_id)); CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY,name TEXT UNIQUE,role TEXT,room_id INTEGER,event_id INTEGER,operator TEXT,online_status TEXT,last_heartbeat TEXT,app_version TEXT); CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,scope TEXT,scope_id INTEGER,sender TEXT,body TEXT,priority TEXT,created_at TEXT); CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY,message_id INTEGER,original_name TEXT,stored_name TEXT,mime_type TEXT,size INTEGER); CREATE TABLE IF NOT EXISTS help_requests(id INTEGER PRIMARY KEY,event_id INTEGER,room_id INTEGER,room_name TEXT,requested_by TEXT,category TEXT,description TEXT,priority TEXT,status TEXT,assigned_to TEXT,created_at TEXT,acknowledged_at TEXT,resolved_at TEXT);''')
  c.execute("INSERT OR IGNORE INTO settings VALUES('venue_name','Harrogate Convention Centre')"); c.execute("INSERT OR IGNORE INTO settings VALUES('control_centre_name','Speaker Preview')")
  if c.execute('SELECT COUNT(*) n FROM rooms').fetchone()['n']==0:
   rooms=[("Queen's Suite 1",'QS1','ready'),("Queen's Suite 2",'QS2','live'),("Queen's Suite 3",'QS3','technical_issue'),("Queen's Suite 4",'QS4','setting_up'),("Queen's Suite 5",'QS5','ready'),("Queen's Suite 6",'QS6','rehearsal'),('Auditorium','AUD','live')]; c.executemany('INSERT INTO rooms(name,short_name,current_status) VALUES(?,?,?)',rooms)
   e1=c.execute("INSERT INTO events(name,client,event_color,starts_at,ends_at,event_status) VALUES(?,?,?,?,?,'live')",('NHS Conference','NHS England','#8b5cf6','2026-08-09T08:00','2026-08-09T17:00')).lastrowid; e2=c.execute("INSERT INTO events(name,client,event_color,starts_at,ends_at,event_status) VALUES(?,?,?,?,?,'live')",('Bird Association Meeting','RSPB','#22a7f0','2026-08-09T09:00','2026-08-09T16:00')).lastrowid
   for r in c.execute('SELECT id,name FROM rooms').fetchall(): c.execute('INSERT INTO event_rooms VALUES(?,?)',(e2 if r['name']=='Auditorium' else e1,r['id']))
   q3=c.execute("SELECT id FROM rooms WHERE short_name='QS3'").fetchone()['id']; c.execute('INSERT INTO help_requests(event_id,room_id,room_name,requested_by,category,description,priority,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(e1,q3,"Queen's Suite 3",'Demo User','Presentation',"Presenter laptop is not displaying through HDMI.",'urgent','new',now()))
   for name,role,short in [('QS3-Main','main','QS3'),('QS1-Backup','backup','QS1'),('Control-Centre-01','control_centre',None),('QS1-Main','main','QS1')]:
    rid=c.execute('SELECT id FROM rooms WHERE short_name=?',(short,)).fetchone()['id'] if short else None; c.execute('INSERT INTO devices(name,role,room_id,online_status,last_heartbeat,app_version) VALUES(?,?,?,?,?,?)',(name,role,rid,'online',now(),VERSION))
init()
class Hub:
 def __init__(self): self.ws=set()
 async def emit(self,p):
  dead=[]
  for w in list(self.ws):
   try: await w.send_json(p)
   except: dead.append(w)
  for w in dead:self.ws.discard(w)
hub=Hub()
class Message(BaseModel): scope:str; scope_id:int|None=None; sender:str; body:str=''; priority:str='normal'
class Help(BaseModel): event_id:int|None=None; room_id:int|None=None; requested_by:str; category:str; description:str; priority:str='important'
class Device(BaseModel): name:str; role:str='general'; room_id:int|None=None; event_id:int|None=None; operator:str=''; app_version:str=''
@app.get('/',response_class=HTMLResponse)
def home(): return HTMLResponse((Path(__file__).parent/'static'/'index.html').read_text())
@app.get('/api/health')
def health(): return {'status':'ok','version':VERSION}
@app.get('/api/bootstrap')
def boot():
 with db() as c:return {'version':VERSION,'settings':{r['key']:r['value'] for r in c.execute('SELECT * FROM settings')},'rooms':[dict(r) for r in c.execute('SELECT * FROM rooms WHERE enabled=1 ORDER BY name')],'events':[dict(r) for r in c.execute('SELECT * FROM events WHERE archived=0 ORDER BY starts_at')],'event_rooms':[dict(r) for r in c.execute('SELECT * FROM event_rooms')],'devices':[dict(r) for r in c.execute('SELECT * FROM devices ORDER BY name')],'help_requests':[dict(r) for r in c.execute("SELECT * FROM help_requests WHERE status NOT IN ('resolved','cancelled') ORDER BY id DESC")]}
@app.get('/api/messages')
def messages(scope:str,scope_id:int|None=None):
 with db() as c:
  rows=c.execute("SELECT * FROM messages WHERE scope='venue' ORDER BY id DESC LIMIT 200") if scope=='venue' else c.execute('SELECT * FROM messages WHERE scope=? AND scope_id=? ORDER BY id DESC LIMIT 200',(scope,scope_id)); out=[]
  for r in reversed(rows.fetchall()): d=dict(r); d['attachments']=[dict(a) for a in c.execute('SELECT * FROM attachments WHERE message_id=?',(r['id'],))]; out.append(d)
  return out
@app.post('/api/messages')
async def add_message(m:Message):
 with db() as c: mid=c.execute('INSERT INTO messages(scope,scope_id,sender,body,priority,created_at) VALUES(?,?,?,?,?,?)',(m.scope,m.scope_id,m.sender,m.body,m.priority,now())).lastrowid; d=dict(c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone()); d['attachments']=[]
 await hub.emit({'type':'message','message':d}); return d
@app.post('/api/messages/{mid}/attachments')
async def attach(mid:int,file:UploadFile=File(...)):
 name=''.join(x for x in file.filename if x.isalnum() or x in '._- ')[:160] or 'file'; stored=uuid.uuid4().hex+'_'+name; dest=UP/stored; size=0
 with dest.open('wb') as f:
  while chunk:=await file.read(1024*1024):
   size+=len(chunk)
   if size>25*1024*1024: f.close(); dest.unlink(missing_ok=True); raise HTTPException(413,'25MB limit')
   f.write(chunk)
 with db() as c:c.execute('INSERT INTO attachments(message_id,original_name,stored_name,mime_type,size) VALUES(?,?,?,?,?)',(mid,file.filename,stored,file.content_type or '',size))
 await hub.emit({'type':'refresh'}); return {'ok':True}
@app.get('/api/attachments/{aid}')
def getattach(aid:int):
 with db() as c:r=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
 if not r: raise HTTPException(404)
 return FileResponse(UP/r['stored_name'],media_type=r['mime_type'] or 'application/octet-stream',filename=r['original_name'])
@app.post('/api/help')
async def add_help(h:Help):
 with db() as c:
  rn=''; rr=c.execute('SELECT name FROM rooms WHERE id=?',(h.room_id,)).fetchone() if h.room_id else None; rn=rr['name'] if rr else ''
  hid=c.execute("INSERT INTO help_requests(event_id,room_id,room_name,requested_by,category,description,priority,status,created_at) VALUES(?,?,?,?,?,?,?,'new',?)",(h.event_id,h.room_id,rn,h.requested_by,h.category,h.description,h.priority,now())).lastrowid
 await hub.emit({'type':'refresh'}); return {'id':hid}
@app.patch('/api/help/{hid}')
async def help_update(hid:int,p:dict):
 with db() as c:
  st=p.get('status');
  if st=='acknowledged': c.execute('UPDATE help_requests SET status=?,acknowledged_at=? WHERE id=?',(st,now(),hid))
  elif st=='resolved': c.execute('UPDATE help_requests SET status=?,resolved_at=? WHERE id=?',(st,now(),hid))
  elif st:c.execute('UPDATE help_requests SET status=? WHERE id=?',(st,hid))
 await hub.emit({'type':'refresh'}); return {'ok':True}
@app.post('/api/devices/register')
async def reg(d:Device):
 with db() as c:c.execute("INSERT INTO devices(name,role,room_id,event_id,operator,online_status,last_heartbeat,app_version) VALUES(?,?,?,?,?,'online',?,?) ON CONFLICT(name) DO UPDATE SET role=excluded.role,room_id=excluded.room_id,event_id=excluded.event_id,operator=excluded.operator,online_status='online',last_heartbeat=excluded.last_heartbeat,app_version=excluded.app_version",(d.name,d.role,d.room_id,d.event_id,d.operator,now(),d.app_version))
 await hub.emit({'type':'refresh'}); return {'ok':True}
@app.post('/api/devices/heartbeat')
def beat(p:dict):
 with db() as c:c.execute("UPDATE devices SET online_status='online',last_heartbeat=? WHERE name=?",(now(),p.get('name','')))
 return {'ok':True}
@app.websocket('/ws')
async def ws(w:WebSocket):
 await w.accept(); hub.ws.add(w)
 try:
  while True: await w.receive_text()
 except WebSocketDisconnect: hub.ws.discard(w)
