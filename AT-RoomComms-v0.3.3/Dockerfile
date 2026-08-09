FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server /app
RUN mkdir -p /data/uploads
EXPOSE 5070
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","5070"]
