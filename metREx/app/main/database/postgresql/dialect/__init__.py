import re

from ssl import SSLContext

from sqlalchemy.dialects.postgresql.pg8000 import PGDialect_pg8000 as BaseDialect


class PostgreSQLDialect(BaseDialect):
    def _get_server_version_info(self, connection):
        v = connection.exec_driver_sql("select pg_catalog.version()").scalar()

        m = re.match(
            r".*(?:PostgreSQL|EnterpriseDB|(?:CockroachDB(?:\s+CCL)?)) "
            r"v?(\d+)\.?(\d+)?(?:\.(\d+))?(?:\.\d+)?(?:devel|beta)?",
            v
        )

        if not m:
            raise AssertionError(
                "Could not determine version from string '%s'" % v
            )

        return tuple([int(x) for x in m.group(1, 2, 3) if x is not None])

    def create_connect_args(self, url):
        cargs, cparams = super(PostgreSQLDialect, self).create_connect_args(url)

        if 'ssl_cert' in cparams.keys():
            ssl_context = SSLContext()

            if 'ssl_ca' in cparams.keys():
                ssl_context.load_verify_locations(cafile=cparams.pop('ssl_ca'))

            ssl_context.load_cert_chain(
                cparams.pop('ssl_cert'),
                keyfile=cparams.pop('ssl_key') if 'ssl_key' in cparams.keys() else None
            )

            cparams['ssl_context'] = ssl_context

        return cargs, cparams
