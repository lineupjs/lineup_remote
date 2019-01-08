FROM python:3-alpine

LABEL maintainer="Samuel Gratzl <sam@sgratzl.com>"

VOLUME ["/lineup"]
WORKDIR /lineup

RUN apk add --no-cache --update py3-psycopg2 && rm -rf /var/cache/apk/*
# for better layers
RUN pip install sqlalchemy connexion[swagger-ui]

ADD requirements.txt /data/
RUN pip install -r /data/requirements.txt

CMD python3 lineup_remote
EXPOSE 8080
