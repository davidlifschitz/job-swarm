FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY ml_job_swarm ./ml_job_swarm
COPY data ./data
COPY scripts/start-hosted.sh ./scripts/start-hosted.sh

RUN chmod +x ./scripts/start-hosted.sh \
  && uv sync --frozen --no-dev

ENV ML_JOB_SWARM_DATA_DIR=/data \
    ML_JOB_SWARM_DB_PATH=/data/jobs.db \
    ML_JOB_SWARM_RESUME_ASSET_DIR=/data/resume-assets \
    ML_JOB_SWARM_SEED_COMPANIES=data/seed_companies.json \
    PORT=8080

EXPOSE 8080

CMD ["./scripts/start-hosted.sh"]