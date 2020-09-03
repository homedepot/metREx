from sqlalchemy import text


class DatabaseAccessLayer:
    _session = None

    def __init__(self, db):
        self._db = db

    def execute(self, statement):
        result = self._session.execute(text(statement).execution_options(autocommit=False))

        return result

    def init_db(self, bind):
        engine = self._db.get_engine(bind=bind)

        self._session = self._db.create_scoped_session({
            'autocommit': False,
            'autoflush': False,
            'bind': engine
        })
