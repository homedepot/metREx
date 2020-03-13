from ibm_db_sa.ibm_db import DB2Dialect_ibm_db


class MyDB2Dialect(DB2Dialect_ibm_db):
    def get_isolation_level(self, connection):
        return 'CS'

    def create_connect_args(self, url):
        connect_args = super(MyDB2Dialect, self).create_connect_args(url)

        x = list(connect_args)
        y = list(x[0])

        y[0] += 'AUTHENTICATION=SERVER'

        x[0] = tuple(y)
        connect_args = tuple(x)

        return connect_args
