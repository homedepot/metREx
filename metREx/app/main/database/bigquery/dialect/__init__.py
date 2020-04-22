import json

from pybigquery.sqlalchemy_bigquery import BigQueryDialect


class MyBigQueryDialect(BigQueryDialect):
    def create_connect_args(self, url):
        query = url.query

        if 'credentials_info' in query:
            self.credentials_info = json.loads(query.pop('credentials_info'))

            url.query = query

        return super(MyBigQueryDialect, self).create_connect_args(url)
