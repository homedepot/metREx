from sqlalchemy import text


class DatabaseAccessLayer:
    _db_session = None
    _engine = None

    def __init__(self, db):
        self._db = db

    def execute(self, statement):
        result = self._db_session.execute(text(statement).execution_options(autocommit=False))

        self._db_session.rollback()

        return result

    def init_db(self, bind):
        self._engine = self._db.get_engine(bind=bind)

        self._db_session = self._db.create_scoped_session({
            'bind': self._engine
        })

    def __del__(self):
        if self._engine is not None:
            self._engine.dispose()
