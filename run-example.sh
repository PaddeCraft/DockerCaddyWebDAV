#!/bin/bash
docker run --rm -it -p 80:80 -v /:/filesystem -v $(pwd)/config:/config caddy-webdav
