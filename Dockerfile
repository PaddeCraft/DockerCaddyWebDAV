FROM alpine:latest

VOLUME /config
VOLUME /filesystem

RUN mkdir -p /app
COPY entrypoint.py /app/entrypoint.py
COPY config.example.toml /app/config.example.toml

RUN apk update && apk add caddy python3 && caddy add-package github.com/mholt/caddy-webdav

ENTRYPOINT [ "python3", "/app/entrypoint.py" ]