FROM python:3.13-slim
WORKDIR /srv/urna
COPY portal/requirements.txt portal/requirements.txt
RUN pip install --no-cache-dir -r portal/requirements.txt && useradd --uid 10001 --create-home portal
COPY portal portal
COPY URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core
RUN mkdir -p /data && chown portal:portal /data
USER portal
ENV PORTAL_DATA_DIR=/data
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "portal.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--limit-concurrency", "20"]
