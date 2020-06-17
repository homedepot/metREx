import secrets
import unittest

from ..base import BaseTestCase, get_jobs


def get_application_metrics(client):
    return client.get(
        '/metrics',
        content_type='application/json'
    )


def get_job_metrics(client, job_id):
    return client.get(
        '/metrics/' + job_id,
        content_type='application/json'
    )


class TestMetricsBlueprint(BaseTestCase):
    def test_get_application_metrics(self):
        with self.client:
            response = get_application_metrics(self.client)

            self.assertEqual(response.status_code, 200)

    def test_get_job_metrics(self):
        jobs = get_jobs()

        total_jobs = len(jobs)

        if total_jobs:
            job_id = jobs[secrets.randbelow(total_jobs)]

            with self.client:
                response = get_job_metrics(self.client, job_id)

                self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
