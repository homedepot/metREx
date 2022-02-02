import json
import secrets
import unittest

from datetime import datetime

from faker import Faker

from ..base import BaseTestCase
from metREx.app.main.service.metrics_service import db, Metrics, get_metric_info


class Metric(db.Model):
    __bind_key__ = 'TEST'
    __tablename__ = 'metrics'

    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    label1 = db.Column(db.String(255))
    label2 = db.Column(db.String(255))
    ts = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return "<Metric(id='%s')>" % self.id


class TestDatabaseBlueprint(BaseTestCase):
    bind = 'TEST'
    metric = None

    def test_get_database_metrics(self):
        job_list = self.app.config.get('SCHEDULER_JOBS')

        self.assertIsInstance(job_list, list)

        for job in job_list:
            category = job['args'][0]
            job_name = job['args'][1]
            service_names = job['args'][2]
            statement = job['args'][3]
            value_columns = job['args'][4]

            self.assertEqual(category, 'database')
            self.assertIsInstance(job_name, str)
            self.assertIsInstance(service_names, dict)
            self.assertIsInstance(statement, str)
            self.assertIsInstance(value_columns, list)

            database_metrics = Metrics._get_database_metrics(*job['args'][1:])

            self.assertIsInstance(database_metrics, dict)

            for service_name in service_names['source']:
                prefix, instance = get_metric_info(service_name)

                for column in value_columns:
                    metric_name = '%s.%s' % (prefix, column.lower())

                    self.assertIn(metric_name, database_metrics.keys())

                    for json_label_data, info in database_metrics[metric_name].items():
                        label_dict = json.loads(json_label_data)

                        self.assertIsInstance(label_dict, dict)
                        self.assertIsInstance(info, tuple)

                        metric_value = info[0]

                        self.assertIsInstance(metric_value, int)

    def test_metric_created(self):
        if self.metric is not None:
            self.assertIsInstance(self.metric, Metric)

    def setUp(self):
        if self.bind in self.app.config['SQLALCHEMY_BINDS'].keys():
            db.create_all(bind=self.bind)

            self.fake = Faker()

            self.metric = Metric(
                value=secrets.randbelow(255),
                label1=self.fake.text(max_nb_chars=Metric.label1.property.columns[0].type.length),
                label2=self.fake.text(max_nb_chars=Metric.label2.property.columns[0].type.length)
            )

            db.session.add(self.metric)

            db.session.commit()

        super(TestDatabaseBlueprint, self).setUp()

    def tearDown(self):
        super(TestDatabaseBlueprint, self).tearDown()

        if self.bind in self.app.config['SQLALCHEMY_BINDS'].keys():
            db.session.remove()
            db.drop_all(bind=self.bind)


if __name__ == '__main__':
    unittest.main()
