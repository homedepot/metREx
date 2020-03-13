from abc import ABCMeta

from flask import current_app
from flask_testing import TestCase

from app.main.config import config_by_name


class BaseTestCase(TestCase):
    __metaclass__ = ABCMeta

    def create_app(self, config_name='test'):
        jobs = current_app.config.get('JOBS')

        config_obj = config_by_name[config_name]()

        current_app.config.from_object(config_obj)

        current_app.config['JOBS'] = jobs

        return current_app
