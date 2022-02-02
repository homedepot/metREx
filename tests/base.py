import logging

from abc import ABCMeta

from flask_testing import TestCase

from metREx.app.main import *


class BaseTestCase(TestCase):
    __metaclass__ = ABCMeta

    def create_app(self, config_name='test'):
        logging.disable(logging.CRITICAL)

        return create_app(config_name)

    def setUp(self):
        start_scheduler()

    def tearDown(self):
        shutdown_scheduler()

        registries = {}

        app_registry = get_registry(app_registry_name)

        registries[app_registry] = list(app_registry._names_to_collectors.values())

        jobs = get_jobs()

        for job_id in jobs:
            job_registry = get_registry(job_id)

            registries[job_registry] = list(job_registry._names_to_collectors.values())

        for registry, collectors in registries.items():
            for collector in collectors:
                try:
                    registry.unregister(collector)
                except KeyError:
                    pass
