FROM python:3.10-slim-buster

WORKDIR /app
COPY . /app

RUN pip install pipenv && \
    pipenv install --deploy --ignore-pipfile

CMD ["sh", "-c", "pipenv run python app.py $CONFIG_FILEPATH"]
