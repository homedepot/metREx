import json
import os
import yaml

from apscheduler.executors.pool import ProcessPoolExecutor

from cfenv import AppEnv

from dotenv import load_dotenv, find_dotenv

from .util import sqlalchemy_helper
from .util import api_helper
from .util import apscheduler_helper
from .util import prometheus_helper


def get_secret_key(file_path):
    secret_key = ''

    yaml_data = read_yaml_from_file(file_path)

    if yaml_data is not None:
        if 'secret-key' in yaml_data.keys():
            secret_key = yaml_data['secret-key']

    return secret_key


def read_json_from_file(file_path):
    data = None

    real_file_path = os.path.join(basedir, file_path)

    if os.path.isfile(real_file_path):
        with open(real_file_path, 'r') as stream:
            data = json.load(stream)

    return data


def read_yaml_from_file(file_path):
    data = None

    real_file_path = os.path.join(basedir, file_path)

    if os.path.isfile(real_file_path):
        with open(real_file_path, 'r') as stream:
            data = yaml.safe_load(stream)

    return data


def str_to_bool(x):
    x = str(x)

    return x.lower() in ('true', 't', 'yes', 'y', '1')


local_env = False

env_path = find_dotenv()

if env_path != '':
    local_env = load_dotenv(env_path)

basedir = os.path.abspath(os.path.dirname(env_path))

if local_env:
    if os.getenv('VCAP_APPLICATION') is None:
        json_data = read_json_from_file(os.getenv('VCAP_APPLICATION_PATH', 'env/vcap_application.json'))

        if json_data is not None:
            os.environ['VCAP_APPLICATION'] = json.dumps(json_data, separators=(', ', ': '), sort_keys=True)

    if os.getenv('VCAP_SERVICES') is None:
        json_data = read_json_from_file(os.getenv('VCAP_SERVICES_PATH', 'env/vcap_services.json'))

        if json_data is not None:
            os.environ['VCAP_SERVICES'] = json.dumps(json_data, separators=(', ', ': '), sort_keys=True)

app_prefix = 'METREX'

service_prefix = {
    'APIALCHEMY': os.getenv('API_PREFIX', app_prefix + '_API_'),
    'SQLALCHEMY': os.getenv('DB_PREFIX', app_prefix + '_DB_')
}


class Config:
    DEBUG = str_to_bool(os.getenv('DEBUG', True))
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', get_secret_key(os.getenv('SECRET_PATH', 'secrets.yml')))

    ERROR_INCLUDE_MESSAGE = str_to_bool(os.getenv('ERROR_INCLUDE_MESSAGE', True))
    RESTPLUS_MASK_SWAGGER = False
    SWAGGER_UI_REQUEST_DURATION = True

    JOBS_SOURCE_REFRESH_INTERVAL = None

    PUSHGATEWAY = None

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SCHEDULER_API_ENABLED = False

    SCHEDULER_EXECUTORS = {
        'default': {
            'type': 'threadpool',
            'max_workers': int(os.getenv('THREADPOOL_MAX_WORKERS', '20'))
        },
        'processpool': ProcessPoolExecutor(max_workers=int(os.getenv('PROCESSPOOL_MAX_WORKERS', '10')))
    }

    SCHEDULER_JOB_DEFAULTS = {
        'misfire_grace_time': int(os.getenv('MISFIRE_GRACE_TIME', '5'))
    }

    SUSPEND_JOB_ON_FAILURE = str_to_bool(os.getenv('SUSPEND_JOB_ON_FAILURE', False))

    def __init__(self):
        env = AppEnv()

        self.APIALCHEMY_BINDS = {}

        self.apialchemy_binds = api_helper.parse_services_for_binds(service_prefix['APIALCHEMY'], env.services)

        self.SQLALCHEMY_BINDS = {}

        self.sqlalchemy_binds = sqlalchemy_helper.parse_services_for_binds(service_prefix['SQLALCHEMY'], env.services)

        self.JOBS = []

        if os.getenv('JOBS_SOURCE_SERVICE') is not None:
            self.JOBS_SOURCE_REFRESH_INTERVAL = os.getenv('JOBS_SOURCE_REFRESH_INTERVAL', '60')

        job_prefix = os.getenv('JOB_PREFIX', app_prefix + '_JOB_')
        template_prefix = os.getenv('JOB_PREFIX', app_prefix + '_TEMPLATE_')

        self.service_jobs = apscheduler_helper.get_jobs_from_services(job_prefix, template_prefix, env.services)
        self.source_jobs = {}

        self.jobs = self.service_jobs

    def add_jobs_from_source(self, aa):
        if self.JOBS_SOURCE_REFRESH_INTERVAL is not None:
            self.source_jobs = apscheduler_helper.get_jobs_from_source(aa, (service_prefix['APIALCHEMY'], self.APIALCHEMY_BINDS))

            self.jobs = {**self.service_jobs, **self.source_jobs}

    @property
    def apialchemy_binds(self):
        return self._apialchemy_binds

    @apialchemy_binds.setter
    def apialchemy_binds(self, value):
        self._apialchemy_binds = value

        self.APIALCHEMY_BINDS = api_helper.build_bind_dict(self._apialchemy_binds,
                                                           self.SECRET_KEY)

    def set_pushgateway(self, aa):
        self.PUSHGATEWAY = prometheus_helper.get_pushgateway(aa, (service_prefix['APIALCHEMY'], self.APIALCHEMY_BINDS))

    @property
    def sqlalchemy_binds(self):
        return self._sqlalchemy_binds

    @sqlalchemy_binds.setter
    def sqlalchemy_binds(self, value):
        self._sqlalchemy_binds = value

        self.SQLALCHEMY_BINDS = sqlalchemy_helper.build_bind_dict(self._sqlalchemy_binds,
                                                                  self.SECRET_KEY)

    @property
    def jobs(self):
        return self._jobs

    @jobs.setter
    def jobs(self, value):
        self._jobs = value

        self.JOBS = apscheduler_helper.build_job_list(self._jobs,
                                                      (service_prefix['APIALCHEMY'], self._apialchemy_binds),
                                                      (service_prefix['SQLALCHEMY'], self._sqlalchemy_binds))


class DevelopmentConfig(Config):
    ENV = 'development'


class TestingConfig(Config):
    ENV = 'development'
    TESTING = True
    PRESERVE_CONTEXT_ON_EXCEPTION = False


class ProductionConfig(Config):
    DEBUG = str_to_bool(os.getenv('DEBUG', False))

config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig
)
