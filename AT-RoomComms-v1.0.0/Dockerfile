FROM python:3.12-slim
WORKDIR /app

# V1 uses the proven v0.3.3 application as the functional baseline.
COPY AT-RoomComms-v0.3.3/server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY AT-RoomComms-v0.3.3/server /app
COPY AT-RoomComms-v1.0.0/entrypoint.py /app/entrypoint.py

# Brand the served web interface as V1 and make bootstrap failures visible
# instead of silently returning users to the login screen.
RUN python - <<'PY'
from pathlib import Path
p=Path('/app/static/index.html')
s=p.read_text(encoding='utf-8').replace('v0.3.3','v1.0.0')
p.write_text(s,encoding='utf-8')

p=Path('/app/static/app.js')
s=p.read_text(encoding='utf-8')
old="async function load(){try{S.d=await api('/api/bootstrap');showOnly('app');renderChrome();control()}catch(e){token='';localStorage.removeItem('rc_token');showOnly('login')}}"
new="async function load(){try{S.d=await api('/api/bootstrap');showOnly('app');renderChrome();control();return true}catch(e){console.error(e);showOnly('login');const box=document.querySelector('#loginError');if(box)box.textContent='RoomComms could not load: '+e.message;return false}}"
if old in s:
    s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
PY

RUN mkdir -p /data/uploads
EXPOSE 5070
CMD ["uvicorn","entrypoint:app","--host","0.0.0.0","--port","5070"]
