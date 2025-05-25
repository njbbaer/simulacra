FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install uv
RUN uv sync --frozen --no-dev

CMD ["sh", "-c", "uv run python app.py $CONFIG_FILEPATH"]
