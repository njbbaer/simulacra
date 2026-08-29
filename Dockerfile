FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /bin/uv

WORKDIR /app
COPY . /app

RUN uv sync --frozen --no-dev

CMD ["sh", "-c", "exec .venv/bin/python app.py $CONFIG_FILEPATH"]
