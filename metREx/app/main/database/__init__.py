from sqlalchemy import text


class DatabaseAccessLayer:
    _session = None

    def __init__(self, db):
        self._db = db

    def execute(self, statement):
        result = self._session.execute(text(statement))

        return result

    def init_db(self, bind):
        engine = self._db.get_engine(bind=bind)

        options = {}

        backend = engine.url.get_backend_name()

        if backend == 'informix':
            options['isolation_level'] = 'DIRTY READ'

        self._session = self._db.create_scoped_session({
            'autocommit': False,
            'autoflush': False,
            'bind': engine.execution_options(**options)
        })
