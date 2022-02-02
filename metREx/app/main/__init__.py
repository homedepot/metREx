import json
import logging
import traceback
import warnings

from datetime import datetime, timedelta

from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_MAX_INSTANCES, EVENT_JOB_MISSED, EVENT_JOB_SUBMITTED
from apscheduler.schedulers.base import MaxInstancesReachedError

from flask import Flask

from flask_apialchemy import APIAlchemy

from flask_apscheduler import APScheduler

from flask_sqlalchemy import _EngineConnector as _EngineConnectorBase, SQLAlchemy as SQLAlchemyBase

from prometheus_client import generate_latest, Counter, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.utils import INF

from prometheus_flask_exporter import PrometheusMetrics

from pytz_deprecation_shim import PytzUsageWarning

from sqlalchemy.dialects import registry

from werkzeug.middleware.proxy_fix import ProxyFix

from .api.graphite import GraphiteBridge
from .api.pushgateway import Pushgateway
from .api.wavefront import Wavefront

from .config import config_by_name

from .util.prometheus_helper import prometheus_multiproc_dir, get_registry, register_collector, unregister_collector


class _EngineConnector(_EngineConnectorBase):
    def get_options(self, sa_url, echo):
        sa_url, options = super(_EngineConnector, self).get_options(sa_url, echo)

        if sa_url.drivername.startswith('oracle'):
            warnings.filterwarnings("ignore", ".*max_identifier_length.*")

            # options.setdefault('max_identifier_length', 30)

            options.setdefault('connect_args', {
                'events': True
            })

        poolclass = options.get('poolclass')

        if poolclass and poolclass.__name__ in ['NullPool', 'StaticPool']:
            if 'pool_size' in options.keys():
                options.pop('pool_size')

            if 'pool_recycle' in options.keys():
                options.pop('pool_recycle')

        return sa_url, options


class MisfireGraceTimeReachedError(Exception):
    def __init__(self, job):
        super(MisfireGraceTimeReachedError, self).__init__(
            'Job "%s" has reached its maximum grace time of (%d) seconds' %
            (job.id, job.misfire_grace_time))


class TimeoutWarning(RuntimeWarning):
    pass


class SQLAlchemy(SQLAlchemyBase):
    def make_connector(self, app=None, bind=None):
        """Creates the connector for a given state and bind."""
        return _EngineConnector(self, self.get_app(app), bind)


db = SQLAlchemy()
aa = APIAlchemy()

custom_dialect_info = {
    'bigquery': {
        'driver': 'pybigquery',
        'objname': 'BigQueryDialect'
    },
    'db2': {
        'driver': 'ibm_db',
        'objname': 'DB2Dialect'
    },
    'postgresql': {
        'driver': 'pg8000',
        'objname': 'PostgreSQLDialect'
    }
}

for dialect, info in custom_dialect_info.items():
    modulepath = '%s.database.%s.dialect' % (__package__, dialect)

    registry.register(dialect, modulepath, info['objname'])
    registry.register('%s.%s' % (dialect, info['driver']), modulepath, info['objname'])

warnings.filterwarnings("ignore", category=PytzUsageWarning)

aps = APScheduler()

app_registry_name = 'application'

app_registry = get_registry(app_registry_name)

metrics = PrometheusMetrics.for_app_factory(registry=app_registry)

default_job_category = 'internal'

JOB_EXECUTION_TIME = Histogram(
    'metrex_job_execution_seconds',
    'Time spent executing metREx job',
    ['job', 'category'],
    registry=app_registry,
    buckets=(.1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, 60.0, 150.0, 300.0, INF)
)

JOB_FAILURES = Counter(
    'metrex_job_failures_total',
    'Failed metREx job executions',
    ['job', 'category', 'exception'],
    registry=app_registry
)

registered_collectors = {}

job_collector_metrics = {}

job_push_service_names = {}


def create_app(config_name):
    from .. import blueprint

    app = Flask(__name__)

    app.wsgi_app = ProxyFix(app.wsgi_app)

    try:
        config_obj = config_by_name[config_name]()

        app.config.from_object(config_obj)

        if not app.debug:
            logger = logging.getLogger('werkzeug')
            logger.setLevel(logging.ERROR)

        db.init_app(app)
        aa.init_app(app)

        with app.app_context():
            config_obj.add_jobs_from_source(aa)

        app.config.from_object(config_obj)

        aps.init_app(app)
        metrics.init_app(app)

        app.register_blueprint(blueprint)
    except Exception as e:
        app.logger.critical(e)
        exit(1)

    return app


def delete_pushgateway_job_metrics(job_name, services):
    job_collector_registry = get_registry(job_name)

    grouping_key = get_grouping_key(job_name, job_collector_registry)

    if grouping_key is not None:
        for service, service_name in services.items():
            try:
                with aps.app.app_context():
                    dal = Pushgateway(aa)
                    dal.init_aa(service_name)

                    dal.client.delete(job=job_name, grouping_key=grouping_key)

                aps.app.logger.info("Removed metrics for job '" + job_name + "' from Pushgateway service '" + service + "'.")
            except Exception as e:
                aps.app.logger.warning("Failed removing metrics for job '" + job_name + "' from Pushgateway service '" + service + "'.")

                raise e


def get_grouping_key(job_name, job_collector_registry):
    if job_name in registered_collectors.keys():
        if registered_collectors[job_name].instance is None:
            generate_latest(job_collector_registry)

        grouping_key = {
            'job': job_name
        }

        if registered_collectors[job_name].instance:
            grouping_key['instance'] = registered_collectors[job_name].instance
    else:
        grouping_key = None

    return grouping_key


def get_jobs():
    job_list = aps.app.config.get('SCHEDULER_JOBS')

    return [
        job['id'] for job in job_list
    ]


def get_push_services(job_name, service_names=None):
    push_services = {}

    if service_names is not None:
        job_push_service_names[job_name] = service_names

    if job_name in job_push_service_names.keys():
        for vendor, services in aps.app.config['PUSH_SERVICES'].items():
            for service, service_name in services.items():
                if service_name in job_push_service_names[job_name]:
                    if vendor not in push_services.keys():
                        push_services[vendor] = {}

                    push_services[vendor][service] = service_name

    return push_services


def init_job_metric_counters(job_name, category):
    exceptions = [
        MaxInstancesReachedError,
        MisfireGraceTimeReachedError,
        TimeoutWarning
    ]

    for e in exceptions:
        JOB_FAILURES.labels(job_name, category, e.__name__)


def job_completed_event_listener(event):
    aps.app.logger.info("Job '" + event.job_id + "' completed.")


def job_not_executed_event_listener(event):
    job_list = aps.app.config.get('SCHEDULER_JOBS')

    for job in job_list:
        job_name = job['id']
        category = job['args'][0]

        if job_name == event.job_id:
            JOB_EXECUTION_TIME.labels(job_name, category).observe(0.0)

            exception = ''

            if event.code == EVENT_JOB_MAX_INSTANCES:
                exception = MaxInstancesReachedError.__name__
            elif event.code == EVENT_JOB_MISSED:
                exception = MisfireGraceTimeReachedError.__name__

            JOB_FAILURES.labels(job_name, category, exception).inc()
            break


def job_started_event_listener(event):
    aps.app.logger.info("Job '" + event.job_id + "' started.")


def push_graphite_job_metrics(job_name, services):
    job_collector_registry = get_registry(job_name)

    if job_name in registered_collectors.keys():
        if registered_collectors[job_name].instance is None:
            generate_latest(job_collector_registry)

        for service, service_name in services.items():
            try:
                with aps.app.app_context():
                    dal = GraphiteBridge(aa)
                    dal.init_aa(service_name)

                    dal.client.push(registry=job_collector_registry)

                aps.app.logger.info("Sent metrics for job '" + job_name + "' to Graphite bridge service '" + service + "'.")
            except Exception as e:
                aps.app.logger.warning("Failed sending metrics for job '" + job_name + "' to Graphite bridge service '" + service + "'.")

                raise e


def push_pushgateway_job_metrics(job_name, services):
    job_collector_registry = get_registry(job_name)

    grouping_key = get_grouping_key(job_name, job_collector_registry)

    if grouping_key is not None:
        for service, service_name in services.items():
            try:
                with aps.app.app_context():
                    dal = Pushgateway(aa)
                    dal.init_aa(service_name)

                    dal.client.push(job=job_name, registry=job_collector_registry, grouping_key=grouping_key)

                aps.app.logger.info("Sent metrics for job '" + job_name + "' to Pushgateway service '" + service + "'.")
            except Exception as e:
                aps.app.logger.warning("Failed sending metrics for job '" + job_name + "' to Pushgateway service '" + service + "'.")

                raise e


def push_wavefront_job_metrics(job_name, services):
    if job_name in job_collector_metrics.keys():
        default_source = ('prod' if aps.app.env == 'production' else 'dev') + '.monitoring.metrex'

        source = aps.app.config['WAVEFRONT_SOURCE'] or default_source

        for service, service_name in services.items():
            try:
                with aps.app.app_context():
                    dal = Wavefront(aa)
                    dal.init_aa(service_name)

                    dal.client.send(source=source, metrics=job_collector_metrics[job_name])

                aps.app.logger.info("Sent metrics for job '" + job_name + "' to Wavefront service '" + service + "'.")
            except Exception as e:
                aps.app.logger.warning("Failed sending metrics for job '" + job_name + "' to Wavefront service '" + service + "'.")

                raise e


def reload_job(job, run_on_reload=False):
    job_name = job['id']

    try:
        aps.remove_job(job_name)
        aps.add_job(**job)

        aps.app.logger.info("Job '" + job_name + "' reloaded.")
    except Exception as e:
        aps.app.logger.warning("Failed reloading job '" + job_name + "'.")

        raise e

    if run_on_reload:
        aps.run_job(job_name)


def set_job_collector_metrics(job_name, collector_metrics, push_services):
    job_collector_metrics[job_name] = collector_metrics

    if job_name not in registered_collectors.keys():
        use_timestamp = len(push_services) == 0

        registered_collectors[job_name] = JobCollector(job_name, use_timestamp)

        register_collector(job_name, registered_collectors[job_name])


def shutdown_scheduler():
    aps.shutdown()


def start_scheduler(config_name=None):
    aps.start(paused=True)

    aps.add_listener(job_not_executed_event_listener, EVENT_JOB_MAX_INSTANCES | EVENT_JOB_MISSED)
    aps.add_listener(job_started_event_listener, EVENT_JOB_SUBMITTED)
    aps.add_listener(job_completed_event_listener, EVENT_JOB_EXECUTED)

    if config_name is not None:
        initial_run_time = datetime.now()

        job_list = aps.app.config.get('SCHEDULER_JOBS')

        for job in job_list:
            job_name = job['id']
            category = job['args'][0]

            initial_run_time += timedelta(seconds=aps.app.config.get('SCHEDULER_JOB_DELAY_SECONDS'))

            aps.modify_job(job_name, next_run_time=initial_run_time)

            init_job_metric_counters(job_name, category)

        source_refresh_interval = aps.app.config.get('JOBS_SOURCE_REFRESH_INTERVAL')

        if source_refresh_interval is not None:
            source_refresh_job_name = 'SOURCE_REFRESH'

            job_kwargs = {
                'trigger': 'interval',
                'args': [default_job_category, config_name, source_refresh_job_name],
                'seconds': int(source_refresh_interval) * 60
            }

            aps.add_job(source_refresh_job_name, __package__ + ':update_jobs', **job_kwargs)

            init_job_metric_counters(source_refresh_job_name, default_job_category)

        aps.resume()


def unset_job_collector_metrics(job_name):
    if job_name in registered_collectors.keys():
        unregister_collector(job_name, registered_collectors[job_name])

        del registered_collectors[job_name]


def update_jobs(category, config_name, source_refresh_job_name):
    try:
        with JOB_EXECUTION_TIME.labels(source_refresh_job_name, category).time():
            config_obj = config_by_name[config_name]()

            with aps.app.app_context():
                config_obj.add_jobs_from_source(aa)

            job_list = aps.app.config.get('SCHEDULER_JOBS')

            jobs = {}

            for i in range(len(job_list)):
                job_name = job_list[i]['id']

                if job_name not in config_obj.jobs.keys():
                    push_services = get_push_services(job_name)

                    if 'pushgateway' in push_services.keys():
                        delete_pushgateway_job_metrics(job_name, push_services['pushgateway'])

                    unset_job_collector_metrics(job_name)

                    aps.remove_job(job_name)

                    aps.app.logger.info("Job '" + job_name + "' removed.")
                else:
                    jobs[job_name] = job_list[i]

            for i in range(len(config_obj.SCHEDULER_JOBS)):
                job_name = config_obj.SCHEDULER_JOBS[i]['id']

                run_job = True

                if job_name in jobs.keys():
                    run_job = json.dumps(config_obj.SCHEDULER_JOBS[i]) != json.dumps(jobs[job_name])

                    if run_job:
                        push_services = get_push_services(job_name)

                        if 'pushgateway' in push_services.keys():
                            delete_pushgateway_job_metrics(job_name, push_services['pushgateway'])

                        unset_job_collector_metrics(job_name)

                        aps.modify_job(**config_obj.SCHEDULER_JOBS[i])

                        aps.app.logger.info("Job '" + job_name + "' updated.")
                else:
                    aps.add_job(**config_obj.SCHEDULER_JOBS[i])

                    aps.app.logger.info("Job '" + job_name + "' added.")

                if run_job:
                    aps.run_job(job_name)

            aps.app.config.from_object(config_obj)
    except Exception as e:
        exception = e.__class__.__name__

        JOB_FAILURES.labels(source_refresh_job_name, category, exception).inc()

        aps.app.logger.warning("Job '" + source_refresh_job_name + "' failed. " + exception + ": " + str(e))
        aps.app.logger.debug(traceback.format_exc())

        # if aps.app.config.get('SUSPEND_JOB_ON_FAILURE'):
        #     aps.pause_job(source_refresh_job_name)
        #
        # aps.app.logger.warning("Job '" + source_refresh_job_name + "' suspended.")


class JobCollector:
    instance = None

    def __init__(self, job_name, use_timestamp):
        self._job_name = job_name
        self._use_timestamp = use_timestamp

    def collect(self):
        for metric_name, info in job_collector_metrics[self._job_name].items():
            json_label_data = list(info.keys())[0]

            label_dict = json.loads(json_label_data)

            g = GaugeMetricFamily(metric_name.replace('.', '_'), '', labels=label_dict.keys())

            if self.instance is None:
                if 'instance' in label_dict.keys():
                    self.instance = label_dict.pop('instance')
                else:
                    self.instance = ''

            for json_label_data, metric in info.items():
                label_dict = json.loads(json_label_data)

                options = {}

                if self._use_timestamp:
                    options['timestamp'] = metric[1]

                g.add_metric(label_dict.values(), metric[0], **options)

            yield g


__all__ = [
    'JOB_EXECUTION_TIME',
    'JOB_FAILURES',
    'TimeoutWarning',
    'aa',
    'app_registry_name',
    'aps',
    'db',
    'default_job_category',
    'metrics',
    'prometheus_multiproc_dir',
    'create_app',
    'generate_latest',
    'get_jobs',
    'get_push_services',
    'get_registry',
    'push_graphite_job_metrics',
    'push_pushgateway_job_metrics',
    'push_wavefront_job_metrics',
    'set_job_collector_metrics',
    'shutdown_scheduler',
    'start_scheduler',
    'unset_job_collector_metrics'
]
