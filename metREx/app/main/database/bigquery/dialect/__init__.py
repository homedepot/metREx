import json

from pybigquery.sqlalchemy_bigquery import BigQueryDialect as BaseDialect


class BigQueryDialect(BaseDialect):
    supports_statement_cache = False

    def create_connect_args(self, url):
        query = url.query

        if 'credentials_info' in query.keys():
            self.credentials_info = json.loads(query['credentials_info'])

        return super(BigQueryDialect, self).create_connect_args(url)
