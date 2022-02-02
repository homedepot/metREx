import os
import re

from sqlalchemy import text


class DatabaseAccessLayer:
    _session = None

    def __init__(self, db):
        self._db = db

    def _get_default_isolation_level(self, backend_name):
        isolation_level_env_var = re.sub(r'\s+', '_', backend_name).upper() + r'_ISOLATION_LEVEL'

        return os.getenv(isolation_level_env_var)

    def execute(self, statement):
        result = self._session.execute(text(statement))

        return result

    def init_db(self, bind):
        engine = self._db.get_engine(bind=bind)

        options = {}

        backend_name = engine.url.get_backend_name()

        default_isolation_level = self._get_default_isolation_level(backend_name)

        if default_isolation_level is not None:
            options['isolation_level'] = default_isolation_level

        self._session = self._db.create_scoped_session({
            'autocommit': False,
            'autoflush': False,
            'bind': engine.execution_options(**options)
        })
