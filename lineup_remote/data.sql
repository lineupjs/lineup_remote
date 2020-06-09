
DROP TABLE IF EXISTS rows;
DROP SEQUENCE IF EXISTS rows_id_seq;

CREATE SEQUENCE rows_id_seq;

CREATE TABLE rows
(
    id integer NOT NULL DEFAULT nextval('rows_id_seq'::regclass),
    d text,
    a double precision,
    cat character varying(3) ,
    cat2 character varying(2),
    dd date,
    CONSTRAINT rows_pkey PRIMARY KEY (id)
);

INSERT INTO rows(d, a, cat, cat2, dd)
  SELECT concat('Row', generate_series(1, 10000)) as d,
         random() as a,
         (ARRAY['c1','c2','c3'])[ceil(random()*3)] as cat,
         (ARRAY['a1','a2'])[ceil(random()*2)] as cat2,
         cast( now() - '1 year'::interval * random()  as date );

INSERT INTO rows(d) values('Missing');
