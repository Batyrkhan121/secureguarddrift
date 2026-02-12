# Stage 1: builder
FROM python:3.11-slim AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml alembic.ini .
COPY api/ api/
COPY auth/ auth/
COPY cache/ cache/
COPY collector/ collector/
COPY core/ core/
COPY db/ db/
COPY drift/ drift/
COPY gitops/ gitops/
COPY graph/ graph/
COPY integrations/ integrations/
COPY ml/ ml/
COPY policy/ policy/
COPY scripts/ scripts/
COPY dashboard/ dashboard/
RUN pip install --no-cache-dir .

# Stage 2: runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app .
ENV PATH="/opt/venv/bin:$PATH"
RUN mkdir -p data reports \
 && adduser --disabled-password --no-create-home appuser \
 && chown -R appuser:appuser data reports
USER appuser
EXPOSE 8000
ENV WORKERS=2
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
ENTRYPOINT ["sh", "-c", "gunicorn api.server:app -w ${WORKERS} -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 120"]
