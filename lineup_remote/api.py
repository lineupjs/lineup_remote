import logging
from connexion import FlaskApp, NoContent
from model import parse_column_dump, parse_ranking_dump

db_session = None

def _init_db(uri):
  from sqlalchemy import create_engine
  from sqlalchemy.orm import scoped_session, sessionmaker
  engine = create_engine(uri, convert_unicode=True)
  return scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def to_dict(result):
  columns = result.keys()
  return [{c: r[c] for c in columns} for r in result]


def get_desc():
  # TODO derive from DB
  return [
    dict(label='D', type='string', column='d'),
    dict(label='A', type='number', column='a', domain=[0, 1]),
    dict(label='Cat', type='categorical', column='cat', categories=['c1', 'c2', 'c3']),
    dict(label='Cat Label', type='categorical', column='cat2', categories=['a1', 'a2']),
  ]


def get_count():
  return db_session.scalar('select count(*) as c from rows')


def get_rows(ids=None):
  if not ids:
    return to_dict(db_session.execute('select * from rows'))
  return to_dict(db_session.execute('select * from rows where id = any(:ids)', params=dict(ids=ids)))


def post_rows(body):
  return get_rows(body)


def get_row(row_id):
  r = db_session.execute('select * from rows where id = :row_id', params=dict(row_id=row_id))
  r = to_dict(r)
  if not r:
    return NoContent, 404
  return r[0]


def post_sort(body):
  ranking_dump = parse_ranking_dump(body)

  filter_sql, args = ranking_dump.to_filter()

  r = db_session.execute('select id from rows ' + ('where ' + filter_sql if filter_sql else ''), params=args)
  # TODO sort criteria
  ids = [row['id'] for row in r]
  return {
    'groups': [
      {
        'name': 'default group',
        'color': 'gray',
        'order': ids
      }
    ],
    'maxDataIndex': max(ids)
  }


def to_categorical_stats(c, hist):
  lookup = {row['cat']: dict(cat=row['cat'], color='gray', count=row['count']) for row in hist if row['cat'] is not None}
  missing = next((row['count'] for row in hist if row['cat'] is None), 0)
  count = sum((v['count'] for v in lookup.values()))
  categories = ['c1', 'c2', 'c3'] if c.column == 'cat' else ['a1', 'a2']  # TODO generalize

  return dict(
    missing=missing,
    count=count,
    maxBin=max(v['count'] for v in lookup.values()),
    hist=[lookup.get(c, dict(cat=c, color='gray', count=0)) for c in categories]
  )


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
      'missing': stats['missing'],
      'count': stats['count'],
      'maxBin': max(stats['hist']),
      'hist': to_hist(stats['hist'], domain)
    }
    boxplot = {
      'min': stats['min'],
      'q1': stats['q1'],
      'median': stats['median'],
      'q3': stats['q3'],
      'max': stats['max'],
      'outlier': stats['outlier'],
      'whiskerLow': stats['whiskerLow'],
      'whiskerHigh': stats['whiskerHigh'],
      'mean': stats['mean'],
      'missing': stats['missing'],
      'count': stats['count'],
    }
    return s, boxplot

  raw, raw_boxplot = to_stat(stats, c.map.domain)
  normalized, normalized_boxplot = to_stat(normalized_stats, [0, 1])
  return {
    'raw': raw,
    'rawBoxPlot': raw_boxplot,
    'normalized': normalized,
    'normalizedBoxPlot': normalized_boxplot
  }


def to_stats(cols, where = '', params = {}):
  numbers = [c for c in cols if c.type == 'number']
  # compute all numbers at once
  if numbers:
    # always on all data
    bins = number_of_bins(db_session.execute('select count(*) as c from rows').first()['c'])

    keys = ', '.join(['stats({c}, {bins}, {d[0]}, {d[1]}) as stats{i}, stats({n}, {bins}, 0, 1) as nstats{i}'.format(c=c.column, n=c.mapped_column, bins=bins, d=c.map.domain, i=i) for i, c in enumerate(numbers)])
    r = db_session.execute('select {0} from rows {1}'.format(keys, where), params=params).first()
    number_stats = [r['stats{0}'.format(i)] for i in range(len(numbers))]
    number_nstats = [r['nstats{0}'.format(i)] for i in range(len(numbers))]

  def to_stat(c):
    if c.type == 'categorical':
      r = db_session.execute('select {0} as cat, count(*) as count from rows {1} group by {0}'.format(c.column, where), params=params)
      return to_categorical_stats(c, r)
    return None
    # TODO support dates

  return [to_number_stats(c, number_stats.pop(0), number_nstats.pop(0)) if c.type == 'number' else to_stat(c) for c in cols]


def post_stats(body):
  cols = [parse_column_dump(dump) for dump in body]
  return to_stats(cols)


def get_column_stats(column):
  # TODO lookup the column its type and then compute the stats
  return None


def get_column_mapping_sample(column):
  r = db_session.execute('select id from rows limit 100')
  return [row['id'] for row in r]


def get_column_search(column, query):
  r = db_session.execute('select id from rows where {} = :query'.format(column), params=dict(query=query))
  return [row['id'] for row in r]


def post_column_stats(column, body):
  column_dump = parse_column_dump(body)
  return to_stats([column_dump])[0]


def post_ranking_column_stats(column, body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dump = parse_column_dump(body['column'])

  where, args = ranking_dump.to_where()
  return to_stats([column_dump], where, args)[0]


def post_ranking_stats(body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dumps = [parse_column_dump(r) for r in body['columns']]

  where, args = ranking_dump.to_where()
  return to_stats(column_dumps, where, args)


def post_ranking_group_stats(group, body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dumps = [parse_column_dump(r) for r in body['columns']]
  # TODO ranking and group filter
  where, args = ranking_dump.to_where()
  return to_stats(column_dumps, where, args)


def post_ranking_group_column_stats(group, column, body):
  ranking_dump = parse_ranking_dump(body['ranking'])
  column_dump = parse_column_dump(body['column'])
  # TODO ranking and group filter
  where, args = ranking_dump.to_where()
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

