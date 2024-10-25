FROM python:latest

RUN apt-get update && apt-get install -y ffmpeg

RUN pip install --upgrade pip && pip install --upgrade poetry

WORKDIR /viewparty
COPY . .
RUN pip install .

ENTRYPOINT ["viewparty"]
