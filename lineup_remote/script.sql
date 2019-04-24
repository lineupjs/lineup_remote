
--DROP IF EXISTS TABLE rows;
CREATE TABLE rows
(
    id integer NOT NULL DEFAULT nextval('rows_id_seq'::regclass),
    d text,
    a double precision,
    cat character varying(3) ,
    cat2 character varying(2),
    CONSTRAINT rows_pkey PRIMARY KEY (id)
)

INSERT INTO rows(d, a, cat, cat2)
  SELECT concat('Row', generate_series(1, 10000)) as d,
         random() as a,
         (ARRAY['c1','c2','c3'])[ceil(random()*3)] as cat,
         (ARRAY['a1','a2'])[ceil(random()*2)] as cat2;


-- mean,missing,count - hist,maxBin

DROP AGGREGATE IF EXISTS boxplot (double precision);
DROP FUNCTION IF EXISTS compute_boxplot(double precision[]);

CREATE FUNCTION compute_boxplot(arr double precision[])
RETURNS json
AS $$
DECLARE
  percentiles double precision[];
  q1 double precision;
  q3 double precision;
  iqr double precision;
  upper_whisker double precision;
  lower_whisker double precision;
  max_whisker double precision;
  min_whisker double precision;
  outliers double precision[];
BEGIN
  percentiles := percentile_cont(ARRAY[0, 0.25, 0.5, 0.75, 1]) WITHIN GROUP (ORDER BY v ASC) FROM unnest(arr) AS t(v);

  q1 := percentiles[2];
  q3 := percentiles[4];
  iqr := q3 - q1;

  min_whisker := q1 - 1.5 * iqr;
  max_whisker := q3 + 1.5 * iqr;

  lower_whisker := coalesce(min(x), q1) FROM unnest(arr) x WHERE x >= min_whisker AND x < q1;
  upper_whisker := coalesce(max(x), q3) FROM unnest(arr) x WHERE x <= max_whisker AND x > q3;

  outliers := array_agg(v ORDER BY v ASC) FROM unnest(arr) as t(v) WHERE v < min_whisker OR v > max_whisker;

  RETURN json_build_object('min', percentiles[1], 'q1', q1, 'median', percentiles[3], 'q3', q3, 'max', percentiles[5], 'outlier', outliers, 'whiskerLow', lower_whisker, 'whiskerHigh', upper_whisker);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE AGGREGATE boxplot (double precision)
(
    sfunc = array_append,
    stype = double precision[],
    initcond = '{}',
    finalfunc = compute_boxplot
);


-- https://wiki.postgresql.org/wiki/Aggregate_Histogram
-- HISTOGRAM

CREATE OR REPLACE FUNCTION histogram_sfunc(state integer[], val double precision, min_value double precision, max_value double precision, nbuckets integer)
RETURNS integer[]
AS $$
DECLARE
  bucket integer;
  i integer;
BEGIN
  -- do nothing if val is NULL
  IF val IS NULL THEN
     RETURN state;
  END IF;

  -- This will put values in buckets with a 0 bucket for <MIN and a (nbuckets+1) bucket for >=MAX
  bucket := min(max(width_bucket(val, min_value, max_value, nbuckets) - 1, 0), nbuckets);

  -- Init the array with the correct number of 0's so the caller doesn't see NULLs
  IF state[0] IS NULL THEN
    state := array_fill(0, ARRAY[nbuckets], ARRAY[0]);
  END IF;

  state[bucket] := state[bucket] + 1;

  RETURN state;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

DROP AGGREGATE IF EXISTS histogram (double precision, double precision, double precision, integer);
CREATE AGGREGATE histogram (val double precision, min_value double precision, max_value double precision, nbuckets integer) (
       SFUNC = histogram_sfunc,
       STYPE = INTEGER[],
       PARALLEL = SAFE -- Remove line for compatibility with  Postgresql < 9.6
);
