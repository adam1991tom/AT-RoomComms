FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home roomcomms \
    && mkdir -p /data \
    && chown -R roomcomms:roomcomms /data /app
COPY --chown=roomcomms:roomcomms server /app
USER roomcomms
EXPOSE 5070
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5070/api/health', timeout=3)" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5070", "--proxy-headers"]
