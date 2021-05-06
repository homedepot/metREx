import json
import os
import yaml

from apscheduler.executors.pool import ProcessPoolExecutor, ThreadPoolExecutor

from cfenv import AppEnv

from dotenv import load_dotenv

from sqlalchemy.pool import NullPool, SingletonThreadPool

from .util import api_helper
from .util import apscheduler_helper
from .util.misc_helper import str_to_bool
from .util import prometheus_helper
from .util import sqlalchemy_helper


def build_vcap_services_from_dict(data):
    vcap_services = {
        'user_provided': []
    }

    if isinstance(data, dict):
        for service, credentials in data.items():
            if isinstance(credentials, dict):
                vcap_services['user_provided'].append({
                    'name': service,
                    'label': 'user_provided',
                    'credentials': credentials
                })

    return json.dumps(vcap_services, separators=(', ', ': '), sort_keys=True)


def get_real_file_path(file_path):
    return os.path.join(basedir, file_path)


def get_secret_key_from_file(file_path, default_file_path):
    secret_key = ''

    if file_path is None:
        if os.path.isfile(get_real_file_path(default_file_path)):
            file_path = default_file_path

    if file_path is not None:
        yaml_data = read_yaml_from_file(file_path)

        if 'secret-key' in yaml_data.keys():
            secret_key = yaml_data['secret-key']

    return secret_key


def get_services_from_file(file_path, default_file_path):
    services = {}

    if file_path is None:
        if os.path.isfile(get_real_file_path(default_file_path)):
            file_path = default_file_path

    if file_path is not None:
        yaml_data = read_yaml_from_file(file_path)

        services = build_vcap_services_from_dict(yaml_data)

    return services


def read_yaml_from_file(file_path):
    try:
        with open(get_real_file_path(file_path), 'r') as stream:
            data = yaml.safe_load(stream)
    except Exception as err:
        raise ValueError(err)

    return data


basedir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

env_path = os.path.join(basedir, '.env')

if os.path.isfile(env_path):
    load_dotenv(env_path)

app_prefix = 'METREX'

service_prefix = {
    'APIALCHEMY': os.getenv('API_PREFIX', app_prefix + '_API_'),
    'SQLALCHEMY': os.getenv('DB_PREFIX', app_prefix + '_DB_')
}

job_prefix = os.getenv('JOB_PREFIX', app_prefix + '_JOB_')
template_prefix = os.getenv('JOB_PREFIX', app_prefix + '_TEMPLATE_')


class Config:
    DEBUG = str_to_bool(os.getenv('DEBUG', True))
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', get_secret_key_from_file(os.getenv('SECRET_PATH'), 'secrets.yml'))

    ERROR_INCLUDE_MESSAGE = str_to_bool(os.getenv('ERROR_INCLUDE_MESSAGE', True))
    RESTPLUS_MASK_SWAGGER = False
    SWAGGER_UI_REQUEST_DURATION = True

    JOBS_SOURCE_REFRESH_INTERVAL = None

    PUSHGATEWAYS = {}

    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,
        'pool_reset_on_return': None
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SCHEDULER_API_ENABLED = False

    SCHEDULER_EXECUTORS = {
        'default': ThreadPoolExecutor(max_workers=int(os.getenv('THREADPOOL_MAX_WORKERS', '20'))),
        'processpool': ProcessPoolExecutor(max_workers=int(os.getenv('PROCESSPOOL_MAX_WORKERS', '10')))
    }

    SCHEDULER_JOB_DEFAULTS = {
        'misfire_grace_time': int(os.getenv('MISFIRE_GRACE_TIME', '5'))
    }

    SCHEDULER_JOB_DELAY_SECONDS = int(os.getenv('JOB_INITIAL_DELAY_SECONDS', '10'))

    SUSPEND_JOB_ON_FAILURE = str_to_bool(os.getenv('SUSPEND_JOB_ON_FAILURE', False))

    def __init__(self):
        if os.getenv('VCAP_SERVICES') is None:
            os.environ['VCAP_SERVICES'] = get_services_from_file(os.getenv('SERVICES_PATH'), 'env/services.yml')

        env = AppEnv()

        self.APIALCHEMY_BINDS = {}

        self.apialchemy_binds = api_helper.parse_services_for_binds(service_prefix['APIALCHEMY'], env.services)

        self.SQLALCHEMY_BINDS = {}

        self.sqlalchemy_binds = sqlalchemy_helper.parse_services_for_binds(service_prefix['SQLALCHEMY'], env.services)

        self.SCHEDULER_JOBS = []

        if os.getenv('JOBS_SOURCE_SERVICE') is not None:
            self.JOBS_SOURCE_REFRESH_INTERVAL = os.getenv('JOBS_SOURCE_REFRESH_INTERVAL', '60')

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

        self.APIALCHEMY_BINDS = api_helper.build_bind_dict(
            self._apialchemy_binds,
            self.SECRET_KEY
        )

    def set_pushgateways(self, aa):
        self.PUSHGATEWAYS = prometheus_helper.get_pushgateways(aa, (service_prefix['APIALCHEMY'], self.APIALCHEMY_BINDS))

    @property
    def sqlalchemy_binds(self):
        return self._sqlalchemy_binds

    @sqlalchemy_binds.setter
    def sqlalchemy_binds(self, value):
        self._sqlalchemy_binds = value

        self.SQLALCHEMY_BINDS = sqlalchemy_helper.build_bind_dict(
            self._sqlalchemy_binds,
            self.SECRET_KEY
        )

    @property
    def jobs(self):
        return self._jobs

    @jobs.setter
    def jobs(self, value):
        self._jobs = value

        self.SCHEDULER_JOBS = apscheduler_helper.build_job_list(
            self._jobs,
            (service_prefix['APIALCHEMY'], self._apialchemy_binds),
            (service_prefix['SQLALCHEMY'], self._sqlalchemy_binds)
        )


class DevelopmentConfig(Config):
    ENV = 'development'


class TestingConfig(Config):
    ENV = 'development'
    TESTING = True
    PRESERVE_CONTEXT_ON_EXCEPTION = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': SingletonThreadPool
    }

    def __init__(self):
        database_service_name = service_prefix['SQLALCHEMY'] + 'TEST'

        services = {
            database_service_name: {
                'dialect': 'sqlite'
            },
            job_prefix + 'QUERY': {
                'services': [
                    database_service_name
                ],
                'interval_minutes': 0,
                'statement': 'SELECT value AS "metric", label1, label2, ts FROM metrics',
                'value_columns': 'metric',
                'static_labels': 'static:test',
                'timestamp_column': 'ts'
            }
        }

        os.environ['VCAP_SERVICES'] = build_vcap_services_from_dict(services)

        if os.getenv('JOBS_SOURCE_SERVICE') is not None:
            del os.environ['JOBS_SOURCE_SERVICE']

        super(TestingConfig, self).__init__()


class ProductionConfig(Config):
    DEBUG = str_to_bool(os.getenv('DEBUG', False))

    ERROR_INCLUDE_MESSAGE = str_to_bool(os.getenv('ERROR_INCLUDE_MESSAGE', False))


config_by_name = dict(
    dev=DevelopmentConfig,
    test=TestingConfig,
    prod=ProductionConfig
)
