import logging
import connexion

db_session = None

def _init_db(uri):
  from sqlalchemy import create_engine
  from sqlalchemy.orm import scoped_session, sessionmaker
  engine = create_engine(uri, convert_unicode=True)
  return scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def get_row(row_id):
  return None


def get_rows(ids=None):
  return []



logging.basicConfig(level=logging.INFO)
db_session = _init_db('sqlite:///:memory:')
app = connexion.FlaskApp(__name__)
app.add_api('openapi.yaml')



@app.app.teardown_appcontext
def shutdown_session(exception=None):
  db_session.remove()

