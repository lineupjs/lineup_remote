import logging
from connexion import FlaskApp, NoContent

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
  return [
    dict(label='D', type='string', column='d'),
    dict(label='A', type='number', column='a', domain=[0, 1]),
    dict(label='Cat', type='categorical', column='cat', categories=['c1', 'c2', 'c3']),
    dict(label='Cat Label', type='categorical', column='cat2', categories=['a1', 'a2']),
  ]


def get_count():
  r = db_session.execute('select count(*) as c from rows')
  return to_dict(r)[0]['c']


def get_rows(ids=None):
  if not ids:
    return to_dict(db_session.execute('select * from rows'))
  return to_dict(db_session.execute('select * from rows where id = any(:ids)', params=dict(ids=ids)))


def get_row(row_id):
  r = db_session.execute('select * from rows where id = :row_id', params=dict(row_id=row_id))
  r = to_dict(r)
  if not r:
    return NoContent, 404
  return r[0]


def post_stats(body):
  return None


def post_stats(body):
  return None


def get_column_stats(column):
  return None


def get_column_mapping_sample(column):
  return None


def get_column_search(column):
  return None


def post_column_stats(column, body):
  return None


def post_ranking_column_stats(column, body):
  return None


def post_ranking_stats(body):
  return None


def post_ranking_group_stats(group, body):
  return None


def post_ranking_group_column_stats(group, column, body):
  return None


logging.basicConfig(level=logging.INFO)
db_session = _init_db('postgresql://lineup:lineup@postgres/lineup')
app = FlaskApp(__name__)
app.add_api('lineup.yaml')



@app.app.teardown_appcontext
def shutdown_session(exception=None):
  db_session.remove()

