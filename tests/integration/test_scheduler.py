import json
import secrets
import unittest

from datetime import datetime

from faker import Faker

from ..base import BaseTestCase
from metREx.app.main import db


def get_info(client):
    return client.get(
        '/scheduler',
        content_type='application/json'
    )


def get_job(client, job_id):
    return client.get(
        '/scheduler/jobs/' + job_id,
        content_type='application/json'
    )


def get_jobs(client):
    return client.get(
        '/scheduler/jobs',
        content_type='application/json'
    )


def pause_job(client, job_id):
    return client.get(
        '/scheduler/jobs/' + job_id + '/pause',
        content_type='application/json'
    )


def resume_job(client, job_id):
    return client.get(
        '/scheduler/jobs/' + job_id + '/resume',
        content_type='application/json'
    )


def run_job(client, job_id):
    return client.get(
        '/scheduler/jobs/' + job_id + '/run',
        content_type='application/json'
    )


class Metric(db.Model):
    __bind_key__ = 'TEST'
    __tablename__ = 'metric'

    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    label1 = db.Column(db.String(255))
    label2 = db.Column(db.String(255))
    ts = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return "<Metric(id='%s')>" % self.id


class TestSchedulerBlueprint(BaseTestCase):
    bind = 'TEST'
    metric = None

    def test_get_info(self):
        with self.client:
            response = get_info(self.client)

            self.assertEqual(response.status_code, 200)

    def test_get_job(self):
        with self.client:
            response = get_jobs(self.client)

            jobs = json.loads(response.data)

            total_jobs = len(jobs)

            if total_jobs:
                job_id = jobs[secrets.randbelow(total_jobs)]['id']

                response = get_job(self.client, job_id)

                job = json.loads(response.data)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(job['id'], job_id)

    def test_get_jobs(self):
        with self.client:
            response = get_jobs(self.client)

            self.assertEqual(response.status_code, 200)

    def test_metric_created(self):
        if self.metric is not None:
            self.assertIsInstance(self.metric, Metric)

    def test_pause_job(self):
        with self.client:
            response = get_jobs(self.client)

            jobs = json.loads(response.data)

            total_jobs = len(jobs)

            if total_jobs:
                job_id = jobs[secrets.randbelow(total_jobs)]['id']

                response = pause_job(self.client, job_id)

                job = json.loads(response.data)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(job['id'], job_id)

                if 'next_run_time' in job.keys():
                    self.assertIsNone(job['next_run_time'])

    def test_resume_job(self):
        with self.client:
            response = get_jobs(self.client)

            jobs = json.loads(response.data)

            total_jobs = len(jobs)

            if total_jobs:
                job_id = jobs[secrets.randbelow(total_jobs)]['id']

                response = resume_job(self.client, job_id)

                job = json.loads(response.data)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(job['id'], job_id)

                if 'next_run_time' in job.keys():
                    self.assertIsNotNone(job['next_run_time'])

    def test_run_job(self):
        with self.client:
            response = get_jobs(self.client)

            jobs = json.loads(response.data)

            total_jobs = len(jobs)

            if total_jobs:
                job_id = jobs[secrets.randbelow(total_jobs)]['id']

                response = run_job(self.client, job_id)

                job = json.loads(response.data)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(job['id'], job_id)

    def setUp(self):
        if self.bind in self.app.config['SQLALCHEMY_BINDS'].keys():
            db.create_all(bind=self.bind)

            self.fake = Faker()

            self.metric = Metric(value=secrets.randbelow(255),
                                 label1=self.fake.text(max_nb_chars=Metric.label1.property.columns[0].type.length),
                                 label2=self.fake.text(max_nb_chars=Metric.label2.property.columns[0].type.length))

            db.session.add(self.metric)

            db.session.commit()

    def tearDown(self):
        super(TestSchedulerBlueprint, self).tearDown()

        if self.bind in self.app.config['SQLALCHEMY_BINDS'].keys():
            db.session.remove()
            db.drop_all(bind=self.bind)


if __name__ == '__main__':
    unittest.main()
