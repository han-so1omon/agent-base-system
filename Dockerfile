FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY docs/seed/ ./docs/seed/

RUN pip install --no-cache-dir . uvicorn

EXPOSE 8000

USER 10001

ENTRYPOINT ["python", "-m", "base_agent_system.container"]
CMD ["api"]
