import logging

from abc import ABCMeta

from flask_testing import TestCase

from metREx.manage import app
from metREx.app.main.config import config_by_name


class BaseTestCase(TestCase):
    __metaclass__ = ABCMeta

    def create_app(self, config_name='test'):
        logging.disable(logging.CRITICAL)

        jobs = app.config.get('JOBS')

        config_obj = config_by_name[config_name]()

        app.config.from_object(config_obj)

        app.config['JOBS'] = jobs

        return app
