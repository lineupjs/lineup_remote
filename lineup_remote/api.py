import logging
from connexion import FlaskApp, NoContent
from sqlalchemy.orm import scoped_session
from typing import Any, Dict, List
from .model import parse_column_dump, parse_ranking_dump, parse_compute_column_dump

db_session: scoped_session = None

def _init_db(uri: str) -> scoped_session:
  from sqlalchemy import create_engine
  from sqlalchemy.orm import sessionmaker
  engine = create_engine(uri, convert_unicode=True, echo=True)
  return scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


TABLE = 'rows'


def to_dict(result) -> List[Dict[str, Any]]:
  columns = result.keys()
  return [{c: r[c] for c in columns} for r in result]


def categories_of(column: str):
  return ['c1', 'c2', 'c3'] if column == 'cat' else ['a1', 'a2']  # TODO generalize

def get_desc() -> List[Dict[str, Any]]:
  # TODO derive from DB
  return [
    dict(label='D', type='string', column='d'),
    dict(label='A', type='number', column='a', domain=[0, 1]),
    dict(label='Cat', type='categorical', column='cat', categories=categories_of('cat')),
    dict(label='Cat Label', type='categorical', column='cat2', categories=categories_of('cat2')),
    dict(label='Date', type='date', column='dd', dateFormat='%Y-%m-%d'),
  ]


def get_count() -> int:
  return db_session.scalar('select count(*) as c from {t}'.format(t=TABLE))


def get_rows(ids=None) -> List[Dict[str, Any]]:
  if not ids:
    return to_dict(db_session.execute('select * from {t}'.format(t=TABLE)))
  lookup = {r['id']: r for r in to_dict(db_session.execute('select * from {t} where id = any(:ids)'.format(t=TABLE), params=dict(ids=ids)))}
  # ensure incoming order
  return [lookup.get(id, {}) for id in ids]


def post_rows(body):
  return get_rows(body)


def get_row(row_id):
  r = db_session.execute('select * from {t} where id = :row_id'.format(t=TABLE), params=dict(row_id=row_id))
  r = to_dict(r)
  if not r:
    return NoContent, 404
  return r[0]


def post_sort(body):
  ranking_dump = parse_ranking_dump(body)

  where, args = ranking_dump.to_where()
  order_by = ranking_dump.to_sort()

  if not ranking_dump.group_criteria:
    query = 'select id from {2} {0} {1}'.format(where, order_by, TABLE)
    r = db_session.execute(query, params=args)

    ids = [row['id'] for row in r]
    groups = [
      {
        'name': 'Default group',
        'color': 'gray',
        'order': ids
      }
    ]
  else:
    query = 'select {2} as name, array_agg(id) as ids from {4} {0} {1} group by {3}'.format(where, order_by, ranking_dump.to_group_name(), ', '.join(c.column for c in ranking_dump.group_criteria), TABLE)
    r = db_session.execute(query, params=args)

    groups = [{
        'name': row['name'],
        'color': 'gray',
        'order': row['ids']
     } for row in r]
  return {
    'groups': groups,
    'maxDataIndex': max((max(g['order']) for g in groups))
  }


def to_categorical_stats(c, hist):
  categories = categories_of(c.column)

  missing = hist[-1]
  hist=[dict(cat=cat, color='gray', count=count) for cat, count in zip(categories, hist)]
  count = sum((bin['count'] for bin in hist))

  return dict(
    missing=missing,
    count=count,
    maxBin=max((bin['count'] for bin in hist), default=0),
    hist=hist
  )


def to_date_buckets(min_date, max_date):
  delta = max_date - min_date

  import datetime
  from dateutil.relativedelta import relativedelta

  if delta.days > 365:
    # year mode
    gran = 'year'
    dd = relativedelta(years=1)
    x0 = datetime.date(min_date.year, 1, 1)
  elif delta.days > 30:
    gran = 'month'
    dd = relativedelta(months=1)
    x0 = datetime.date(min_date.year, min_date.month, 1)
  else:
    gran = 'day'
    dd = relativedelta(days=1)
    x0 = datetime.date(min_date.year, min_date.month, min_date.day)

  buckets = []
  while x0 < max_date:
    buckets.append(x0)
    x0 = x0 + dd
  buckets.append(x0)
  return gran, buckets


def to_date_stats(c, stats, granularity, buckets):
  return {
    'min': stats['min'],
    'max': stats['max'],
    'missing': stats['missing'] or 0,
    'count': stats['count'] or 0,
    'maxBin': max(stats['hist'], default=0),
    'hist': [dict(count=bin, x0=buckets[i], x1=buckets[i + 1]) for i, bin in enumerate(stats['hist'])],
    'histGranularity': granularity
  }


def number_of_bins(length):
  if (length == 0):
    return 1
  # as by default used in d3 the Sturges' formula
  import math

  return math.ceil(math.log2(length)) + 1


def to_number_stats(c, stats, normalized_stats):

  def to_hist(hist, domain):
    bins = len(hist)
    x0 = domain[0]
    delta = (domain[1] - domain[0]) / bins
    histogram = []
    for i in range(bins - 1):
      x1 = x0 + delta
      histogram.append(dict(count=hist[i], x0=x0, x1=x1))
      x0 = x1

    # last bin separately to ensure x1 is
    histogram.append(dict(count=hist[-1], x0=x0, x1=domain[1]))
    return histogram

  def to_stat(stats, domain):
    s = {
      'min': stats['min'],
      'max': stats['max'],
      'mean': stats['mean'],
      'missing': stats['missing'] or 0,
      'count': stats['count'] or 0,
      'maxBin': max(stats['hist'], default=0),
      'hist': to_hist(stats['hist'], domain)
    }
    return s

  return {
    'raw': to_stat(stats, c.map.domain),
    'normalized': to_stat(normalized_stats, [0, 1])
  }


def to_boxplot_stats(c, stats, normalized_stats):

  def to_stat(stats):
    boxplot = {
      'min': stats['min'],
      'q1': stats['q1'],
      'median': stats['median'],
      'q3': stats['q3'],
      'max': stats['max'],
      'outlier': stats['outlier'] or [],
      'whiskerLow': stats['whiskerLow'],
      'whiskerHigh': stats['whiskerHigh'],
      'mean': stats['mean'],
      'missing': stats['missing'] or 0,
      'count': stats['count'] or 0,
    }
    return boxplot

  return {
    'raw': to_stat(stats),
    'normalized': to_stat(normalized_stats)
  }


def to_stats(cols, where = '', params = {}):
  dates = [c.dump for c in cols if c.type == 'date']

  keys = ['count(*) as c']
  for i, col in enumerate(dates):
    keys.append('min({0}) as mind{1}'.format(col.column, i))
    keys.append('max({0}) as maxd{1}'.format(col.column, i))
  overall = db_session.execute('select {0} from {1}'.format(', '.join(keys), TABLE)).first()

  bins = number_of_bins(overall['c'])
  date_buckets = [to_date_buckets(overall['mind{0}'.format(i)], overall['maxd{0}'.format(i)]) for i in range(len(dates))]
  print(date_buckets)

  def cats_of(c):
    categories = categories_of(c.column)
    return ', '.join('\'{0}\''.format(c) for c in categories)

  keys = []
  date_index = 0

  for i, col in enumerate(cols):
    c = col.dump
    if col.type == 'number':
      keys.append('stats({c}, {bins}, {d[0]}, {d[1]}) as stats{i}'.format(c=c.column, bins=bins, d=c.map.domain, i=i))
      keys.append('stats({n}, {bins}, 0, 1) as nstats{i}'.format(n=c.mapped_column, bins=bins, i=i))
    elif col.type == 'boxplot':
      keys.append('boxplot({c}) as boxplot{i}'.format(c=c.column, i=i))
      keys.append('boxplot({n}) as nboxplot{i}'.format(n=c.mapped_column, i=i))
    elif col.type == 'categorical':
      keys.append('cathist({c}, ARRAY[{cats}]) as cathist{i}'.format(c=c.column, cats=cats_of(c), i=i))
    elif col.type == 'date':
      _, buckets = date_buckets[date_index]
      date_index += 1
      keys.append('datestats({c}, ARRAY[{bins}]) as dstats{i}'.format(c=c.column, bins=', '.join('date \'' + d.strftime('%Y-%m-%d') + '\'' for d in buckets[1:-1]), i=i))

  r = db_session.execute('select {0} from {2} {1}'.format(', '.join(keys), where, TABLE), params=params).first()

  stats = []
  for i, col in enumerate(cols):
    c = col.dump
    if col.type == 'number':
      sstats = r['stats{i}'.format(i=i)]
      nstats = r['nstats{i}'.format(i=i)]
      stats.append(to_number_stats(c, sstats, nstats))
    elif col.type == 'boxplot':
      boxplot = r['boxplot{i}'.format(i=i)]
      nboxplot = r['nboxplot{i}'.format(i=i)]
      stats.append(to_boxplot_stats(c, boxplot, nboxplot))
    elif col.type == 'categorical':
      cathist = r['cathist{i}'.format(i=i)]
      stats.append(to_categorical_stats(c, cathist))
    elif col.type == 'date':
      dstats = r['dstats{i}'.format(i=i)]
      gran, buckets = date_buckets.pop(0)
      stats.append(to_date_stats(c, dstats, gran, buckets))

  return stats


def post_stats(body):
  cols = [parse_compute_column_dump(dump) for dump in body]
  return to_stats(cols)


def get_column_stats(column):
  # TODO lookup the column its type and then compute the stats
  return None


def get_column_mapping_sample(column):
  r = db_session.execute('select id from {t} limit 100'.format(t=TABLE))
  return [row['id'] for row in r]


def get_column_search(column, query):
  r = db_session.execute('select id from {t} where {c} = :query'.format(c=column, t=TABLE), params=dict(query=query))
  return [row['id'] for row in r]


def post_column_stats(column, body):
  column_dump = parse_compute_column_dump(body)
  return to_stats([column_dump])[0]


def post_ranking_column_stats(column, body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dump = parse_compute_column_dump(body['column'])

  where, args = ranking_dump.to_where()
  return to_stats([column_dump], where, args)[0]


def post_ranking_stats(body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dumps = [parse_compute_column_dump(r) for r in body['columns']]

  where, args = ranking_dump.to_where()
  return to_stats(column_dumps, where, args)


def post_ranking_group_stats(group, body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dumps = [parse_compute_column_dump(r) for r in body['columns']]
  where, args = ranking_dump.to_where(group)
  return to_stats(column_dumps, where, args)


def post_ranking_group_column_stats(group, column, body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dump = parse_compute_column_dump(body['column'])
  where, args = ranking_dump.to_where(group)
  return to_stats([column_dump], where, args)[0]



logging.basicConfig(level=logging.INFO)
db_session = _init_db('postgresql://lineup:lineup@postgres/lineup')
app = FlaskApp(__name__)
app.add_api('openapi.yaml')


@app.app.route('/')
def get_index():
  from flask import send_from_directory
  return send_from_directory('../build', 'index.html')


@app.app.route('/<path:path>')
def get_public(path):
  from flask import send_from_directory
  return send_from_directory('../build', path)


@app.app.teardown_appcontext
def shutdown_session(exception=None):
  db_session.remove()
