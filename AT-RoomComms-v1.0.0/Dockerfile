FROM python:3.12-slim
WORKDIR /app

# V1 uses the proven v0.3.4 application (live chat overhaul) as the functional baseline.
COPY AT-RoomComms-v0.3.3/server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY AT-RoomComms-v0.3.3/server /app
COPY AT-RoomComms-v1.0.0/entrypoint.py /app/entrypoint.py

# Brand the served web interface as V1. Bootstrap-failure visibility is
# handled directly in the shared app.js source, not patched at build time.
RUN python - <<'PY'
from pathlib import Path
p=Path('/app/static/index.html')
s=p.read_text(encoding='utf-8').replace('v0.3.4','v1.0.0')
p.write_text(s,encoding='utf-8')
PY

RUN mkdir -p /data/uploads
EXPOSE 5070
CMD ["uvicorn","entrypoint:app","--host","0.0.0.0","--port","5070"]
