import unittest

from flask import current_app

from ..base import BaseTestCase


class TestDevelopmentConfig(BaseTestCase):
    def create_app(self, config_name='dev'):
        return super(TestDevelopmentConfig, self).create_app(config_name)

    def test_app_is_development(self):
        self.assertFalse(current_app is None)
        self.assertTrue(self.app.env == 'development')
        self.assertFalse(self.app.testing)
        self.assertFalse(self.app.config['RESTPLUS_MASK_SWAGGER'])
        self.assertTrue(self.app.config['SWAGGER_UI_REQUEST_DURATION'])
        self.assertFalse(self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'])
        self.assertFalse(self.app.config['SCHEDULER_API_ENABLED'])


class TestTestingConfig(BaseTestCase):
    def test_app_is_testing(self):
        self.assertFalse(current_app is None)
        self.assertTrue(self.app.env == 'development')
        self.assertTrue(self.app.testing)
        self.assertFalse(self.app.config['RESTPLUS_MASK_SWAGGER'])
        self.assertTrue(self.app.config['SWAGGER_UI_REQUEST_DURATION'])
        self.assertFalse(self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'])
        self.assertFalse(self.app.config['SCHEDULER_API_ENABLED'])
        self.assertFalse(self.app.config['PRESERVE_CONTEXT_ON_EXCEPTION'])


class TestProductionConfig(BaseTestCase):
    def create_app(self, config_name='prod'):
        return super(TestProductionConfig, self).create_app(config_name)

    def test_app_is_production(self):
        self.assertFalse(current_app is None)
        self.assertTrue(self.app.env == 'production')
        self.assertFalse(self.app.testing)
        self.assertFalse(self.app.config['RESTPLUS_MASK_SWAGGER'])
        self.assertTrue(self.app.config['SWAGGER_UI_REQUEST_DURATION'])
        self.assertFalse(self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'])
        self.assertFalse(self.app.config['SCHEDULER_API_ENABLED'])


if __name__ == '__main__':
    unittest.main()
