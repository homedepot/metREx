import logging

from abc import ABCMeta

from flask_testing import TestCase

from metREx.app.main import create_app


class BaseTestCase(TestCase):
    __metaclass__ = ABCMeta

    def create_app(self, config_name='test'):
        logging.disable(logging.CRITICAL)

        return create_app(config_name)
