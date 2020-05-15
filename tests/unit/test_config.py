import unittest

from flask import current_app

from ..base import BaseTestCase


class TestDevelopmentConfig(BaseTestCase):
    def create_app(self, config_name='dev'):
        return super(TestDevelopmentConfig, self).create_app(config_name)

    def test_app_is_development(self):
        self.assertFalse(current_app is None)
        self.assertTrue(current_app.debug)
        self.assertFalse(current_app.testing)
        # self.assertFalse(current_app.config['SECRET_KEY'] == '')


class TestTestingConfig(BaseTestCase):
    def test_app_is_testing(self):
        self.assertFalse(current_app is None)
        self.assertTrue(current_app.debug)
        self.assertTrue(current_app.testing)
        # self.assertFalse(current_app.config['SECRET_KEY'] == '')


class TestProductionConfig(BaseTestCase):
    def create_app(self, config_name='prod'):
        return super(TestProductionConfig, self).create_app(config_name)

    def test_app_is_production(self):
        self.assertFalse(current_app is None)
        self.assertFalse(current_app.debug)
        self.assertFalse(current_app.testing)
        # self.assertFalse(current_app.config['SECRET_KEY'] == '')


if __name__ == '__main__':
    unittest.main()
