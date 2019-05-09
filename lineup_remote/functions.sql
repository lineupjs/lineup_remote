
-- stats aggregation function

DROP TYPE IF EXISTS stats_stype CASCADE;
CREATE TYPE stats_stype AS (hist integer[], missing integer, count integer, min double precision, max double precision, sum double precision);

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
    RETURN state;
	END IF;

  state.count := state.count + 1;
  state.sum := state.sum + val;

  IF state.max IS NULL OR val > state.max THEN
    state.max := val;
  END IF;
  IF state.min IS NULL OR val < state.min THEN
    state.min := val;
  END IF;

  -- This will put values in buckets with a 0 bucket for <MIN and a (nbuckets+1) bucket for >=MAX
  bucket := width_bucket(val, min_hist, max_hist, nbuckets) - 1;
  IF bucket < 0 THEN
    bucket := 0;
  ELSE IF bucket > nbuckets THEN
    bucket := nbuckets;
  END IF;
  END IF;

  state.hist[bucket] := state.hist[bucket] + 1;

	RETURN state;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION stats_ffunc(state stats_stype)
RETURNS json
AS $$
DECLARE
  mean double precision;
BEGIN

  RETURN json_build_object(
    'min', state.min,
    'max', state.max,
    'mean', CASE WHEN state.count = 0 THEN NULL ELSE state.sum / state.count END,
    'count', state.count,
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
    initcond = '({},0,0,,,0)',
    finalfunc = stats_ffunc
);


CREATE OR REPLACE FUNCTION boxplot_ffunc(arr double precision[])
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
  missing integer;
BEGIN

  SELECT
    percentile_cont(ARRAY[0, 0.25, 0.5, 0.75, 1]) WITHIN GROUP (ORDER BY v ASC),
    avg(v),
    sum(CASE WHEN v is null THEN 1 ELSE 0 END)
  INTO percentiles, mean, missing
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
    'count', array_length(arr, 1) - missing,
    'missing', missing
  );
END;
$$ LANGUAGE plpgsql IMMUTABLE;


DROP AGGREGATE IF EXISTS boxplot (double precision);
CREATE AGGREGATE boxplot (val double precision)
(
    sfunc = array_append,
    stype = double precision[],
    initcond = '{}',
    finalfunc = boxplot_ffunc
);


CREATE OR REPLACE FUNCTION cathist_sfunc(state integer[], val varchar, categories varchar[])
RETURNS integer[]
AS $$
DECLARE
  len integer;
  i integer;
  x varchar;
BEGIN
  len := array_length(categories, 1);
  -- Init the array with the correct number of 0's so the caller doesn't see NULLs
  IF state[0] IS NULL THEN
    state := array_fill(0, ARRAY[len + 1], ARRAY[0]);
  END IF;

  IF val IS NULL THEN
    state[len] := state[len] + 1;
    RETURN state;
	END IF;

  i := 0;

  FOREACH x IN ARRAY categories LOOP
    IF x = val THEN
      state[i] := state[i] + 1;
      RETURN state;
    END IF;
    i := i + 1;
  END LOOP;

  state[len] := state[len] + 1; -- count as missing
	RETURN state;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


DROP AGGREGATE IF EXISTS cathist (varchar, categories varchar[]);
CREATE AGGREGATE cathist (val varchar, categories varchar[])
(
    sfunc = cathist_sfunc,
    stype = integer[],
    initcond = '{}'
);

DROP TYPE IF EXISTS datestats_stype CASCADE;
CREATE TYPE datestats_stype AS (hist integer[], missing integer, count integer, min date, max date);

CREATE OR REPLACE FUNCTION datestats_sfunc(state datestats_stype, val date, bucket_ends date[])
RETURNS datestats_stype
AS $$
DECLARE
  nbuckets integer;
  x date;
  i integer;
BEGIN
  nbuckets := array_length(bucket_ends, 1) + 1;

  -- Init the array with the correct number of 0's so the caller doesn't see NULLs
  IF state.hist[0] IS NULL THEN
    state.hist := array_fill(0, ARRAY[nbuckets], ARRAY[0]);
  END IF;

	IF val IS NULL THEN
		state.missing := state.missing + 1;
    RETURN state;
	END IF;

  state.count := state.count + 1;

  IF state.max IS NULL OR val > state.max THEN
    state.max := val;
  END IF;
  IF state.min IS NULL OR val < state.min THEN
    state.min := val;
  END IF;

  i := 0;
  FOREACH x IN ARRAY bucket_ends LOOP
    IF val < x THEN
      state.hist[i] := state.hist[i] + 1;
      RETURN state;
    END IF;
    i := i + 1;
  END LOOP;
  -- add to last one
  state.hist[i] := state.hist[i] + 1;

	RETURN state;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION datestats_ffunc(state datestats_stype)
RETURNS json
AS $$
BEGIN

  RETURN json_build_object(
    'min', state.min,
    'max', state.max,
    'count', state.count,
    'missing', state.missing,
    'hist', state.hist
  );
END;
$$ LANGUAGE plpgsql IMMUTABLE;


DROP AGGREGATE IF EXISTS datestats (date, date[]);
CREATE AGGREGATE datestats (val date, bucket_ends date[])
(
    sfunc = datestats_sfunc,
    stype = datestats_stype,
    initcond = '({},0,0,,)',
    finalfunc = datestats_ffunc
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
