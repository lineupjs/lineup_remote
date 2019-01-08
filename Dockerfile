FROM python:3-alpine

LABEL maintainer="Samuel Gratzl <sam@sgratzl.com>"

VOLUME ["/backup"]
WORKDIR /backup
ENTRYPOINT ["/bin/bash"]

RUN apk add --no-cache --update bash py3-psycopg2 && rm -rf /var/cache/apk/*
# for better layers
RUN pip install sqlalchemy connexion[swagger-ui]

ADD requirements.txt /data/
RUN pip install -r /data/requirements.txt
