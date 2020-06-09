FROM uroybd/python3-psycopg2-alpine:3.7

LABEL maintainer="Samuel Gratzl <sam@sgratzl.com>"

VOLUME ["/lineup"]
WORKDIR /lineup

# for better layers
RUN pip3 install sqlalchemy connexion[swagger-ui]

ADD requirements.txt /data/
RUN pip3 install -r /data/requirements.txt

CMD python3 -m lineup_remote
EXPOSE 8080
