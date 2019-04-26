
-- stats aggregation function

DROP TYPE IF EXISTS stats_stype CASCADE;
CREATE TYPE stats_stype AS (values double precision[], hist integer[], missing integer);

CREATE OR REPLACE FUNCTION stats_sfunc(state stats_stype, val double precision, nbuckets integer, min_hist double precision, max_hist double precision)
RETURNS stats_stype
AS $$
DECLARE
  bucket integer;
  i integer;
BEGIN
  -- Init the array with the correct number of 0's so the caller doesn't see NULLs
  IF state.hist[0] IS NULL THEN
    state.hist := array_fill(0, ARRAY[nbuckets], ARRAY[0]);
  END IF;

	IF val IS NULL THEN
		state.missing := state.missing + 1;
	ELSE
		state.values := array_append(state.values, val);
		-- This will put values in buckets with a 0 bucket for <MIN and a (nbuckets+1) bucket for >=MAX
    bucket := width_bucket(val, min_hist, max_hist, nbuckets) - 1;
    IF bucket < 0 THEN
      bucket := 0;
    ELSE IF bucket > nbuckets THEN
      bucket := nbuckets;
    END IF;
    END IF;

    state.hist[bucket] := state.hist[bucket] + 1;
	END IF;
	RETURN state;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION stats_ffunc(state stats_stype)
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
  mean double precision;
  arr double precision[];
BEGIN
  arr := state.values;

  SELECT
    percentile_cont(ARRAY[0, 0.25, 0.5, 0.75, 1]) WITHIN GROUP (ORDER BY v ASC), avg(v)
  INTO percentiles, mean
  FROM unnest(arr) AS t(v);

  q1 := percentiles[2];
  q3 := percentiles[4];
  iqr := q3 - q1;

  min_whisker := q1 - 1.5 * iqr;
  max_whisker := q3 + 1.5 * iqr;

  lower_whisker := coalesce(min(x), q1) FROM unnest(arr) x WHERE x >= min_whisker AND x < q1;
  upper_whisker := coalesce(max(x), q3) FROM unnest(arr) x WHERE x <= max_whisker AND x > q3;

  outliers := array_agg(v ORDER BY v ASC) FROM unnest(arr) as t(v) WHERE v < min_whisker OR v > max_whisker;

  RETURN json_build_object(
    'min', percentiles[1],
    'q1', q1,
    'median', percentiles[3],
    'q3', q3,
    'max', percentiles[5],
    'outlier', outliers,
    'whiskerLow', lower_whisker,
    'whiskerHigh', upper_whisker,
    'mean', mean,
    'count', array_length(arr, 1),
    'missing', state.missing,
    'hist', state.hist
  );
END;
$$ LANGUAGE plpgsql IMMUTABLE;


DROP AGGREGATE IF EXISTS stats (double precision, integer, double precision, double precision);
CREATE AGGREGATE stats (val double precision, nbuckets integer, min_hist double precision, max_hist double precision)
(
    sfunc = stats_sfunc,
    stype = stats_stype,
    initcond = '({},{},0)',
    finalfunc = stats_ffunc
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
  bucket := width_bucket(val, min_value, max_value, nbuckets) - 1;
  IF bucket < 0 THEN
    bucket := 0;
  ELSE IF bucket > nbuckets THEN
    bucket := nbuckets;
  END IF;
  END IF;

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


-- MAPPING functions

CREATE OR REPLACE FUNCTION map_value(val double precision, type text, domain0 double precision, domain1 double precision, range0 double precision, range1 double precision)
RETURNS double precision
AS $$
DECLARE
  normalized double precision;
  v double precision;
  d0 double precision;
  d1 double precision;
BEGIN
  CASE type
  WHEN 'log' THEN
    v := ln(val);
    d0 := ln(domain0);
    d1 := ln(domain1);
  WHEN 'sqrt' THEN
    v := sqrt(val);
    d0 := sqrt(domain0);
    d1 := sqrt(domain1);
  WHEN 'pow1.1' THEN
    v := power(val, 1.1);
    d0 := power(domain0, 1.1);
    d1 := power(domain1, 1.1);
  WHEN 'pow2' THEN
    v := power(val, 2);
    d0 := power(domain0, 2);
    d1 := power(domain1, 2);
  WHEN 'pow3' THEN
    v := power(val, 3);
    d0 := power(domain0, 3);
    d1 := power(domain1, 3);
  ELSE
    v := val;
    d0 := domain0;
    d1 := domain1;
  END CASE;

  normalized := (v - d0) / (d1 - d0);

  RETURN normalized * (range1 - range0) + range0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
