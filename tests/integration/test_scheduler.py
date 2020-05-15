import json
import secrets
import unittest

from ..base import BaseTestCase


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


class TestSchedulerBlueprint(BaseTestCase):
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


if __name__ == '__main__':
    unittest.main()
