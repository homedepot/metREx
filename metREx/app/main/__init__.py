import json
import logging

from datetime import datetime, timedelta

from flask import Flask
from flask_apialchemy import APIAlchemy
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy

from prometheus_client import generate_latest
from prometheus_client.core import GaugeMetricFamily

from prometheus_flask_exporter import PrometheusMetrics

from sqlalchemy.dialects import registry

from werkzeug.middleware.proxy_fix import ProxyFix

from .config import config_by_name

from .util.prometheus_helper import prometheus_multiproc_dir, get_registry, register_collector, unregister_collector

db = SQLAlchemy()
aa = APIAlchemy()

registry.register('bigquery', __package__ + '.database.bigquery.dialect', 'MyBigQueryDialect')
registry.register('bigquery.pybigquery', __package__ + '.database.bigquery.dialect', 'MyBigQueryDialect')
registry.register('db2', __package__ + '.database.db2.dialect', 'MyDB2Dialect')
registry.register('db2.ibm_db_sa', __package__ + '.database.db2.dialect', 'MyDB2Dialect')

aps = APScheduler()

app_registry_name = 'application'

metrics = PrometheusMetrics.for_app_factory(registry=get_registry(app_registry_name))

registered_collectors = {}

job_collector_metrics = {}


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

            # app.logger.setLevel(logging.ERROR)

        db.init_app(app)
        aa.init_app(app)

        with app.app_context():
            config_obj.add_jobs_from_source(aa)

        app.config.from_object(config_obj)

        aps.init_app(app)
        metrics.init_app(app)

        app.register_blueprint(blueprint)
    except ValueError as error:
        app.logger.critical(error)
        exit(1)

    return app


def delete_job(job_name, pushgateways):
    if job_name in registered_collectors.keys():
        if len(pushgateways):
            options = {
                'grouping_key': {
                    'job': job_name
                }
            }

            if registered_collectors[job_name].instance:
                options['grouping_key']['instance'] = registered_collectors[job_name].instance

            for service, pushgateway in pushgateways.items():
                try:
                    pushgateway.delete(job=job_name, **options)
                except Exception as e:
                    aps.app.logger.warning("Failed removing metrics for job '" + job_name + "' from Pushgateway service '" + service + "'. " + type(e).__name__ + ": " + str(e))

        unregister_collector(job_name, registered_collectors[job_name])

        del registered_collectors[job_name]


def get_jobs():
    job_list = aps.app.config.get('SCHEDULER_JOBS')

    return [
        job['id'] for job in job_list
    ]


def init_scheduler(config_name):
    try:
        job_list = aps.app.config.get('SCHEDULER_JOBS')

        config_obj = config_by_name[config_name]()

        with aps.app.app_context():
            config_obj.set_pushgateways(aa)

        aps.app.config.from_object(config_obj)

        aps.app.config['SCHEDULER_JOBS'] = job_list

        source_refresh_interval = aps.app.config.get('JOBS_SOURCE_REFRESH_INTERVAL')

        if source_refresh_interval is not None:
            source_refresh_job_name = 'SOURCE_REFRESH'

            job_kwargs = {
                'trigger': 'interval',
                'args': [source_refresh_job_name, config_name],
                'seconds': int(source_refresh_interval) * 60
            }

            aps.add_job(source_refresh_job_name, __package__ + ':update_jobs', **job_kwargs)
    except ValueError as error:
        aps.app.logger.critical(error)
        exit(1)


def set_job_collector_metrics(job_name, collector_metrics):
    job_collector_metrics[job_name] = collector_metrics

    if job_name not in registered_collectors:
        registered_collectors[job_name] = JobCollector(job_name)

        register_collector(job_name, registered_collectors[job_name])

    pushgateways = aps.app.config.get('PUSHGATEWAYS')

    if len(pushgateways):
        job_collector_registry = get_registry(job_name)

        if registered_collectors[job_name].instance is None:
            generate_latest(job_collector_registry)

        options = {
            'grouping_key': {
                'job': job_name
            }
        }

        if registered_collectors[job_name].instance:
            options['grouping_key']['instance'] = registered_collectors[job_name].instance

        for service, pushgateway in pushgateways.items():
            try:
                pushgateway.push(job=job_name, registry=job_collector_registry, **options)

                aps.app.logger.info("Sent metrics for job '" + job_name + "' to Pushgateway service '" + service + "'.")
            except Exception as e:
                aps.app.logger.warning("Failed sending metrics for job '" + job_name + "' to Pushgateway service '" + service + "'. " + type(e).__name__ + ": " + str(e))


def shutdown_scheduler():
    aps.shutdown()


def start_scheduler(run_jobs=True):
    aps.start()

    initial_run_time = datetime.now() + timedelta(seconds=5)

    for job_name in get_jobs():
        if run_jobs:
            aps.modify_job(job_name, next_run_time=initial_run_time)
        else:
            aps.pause_job(job_name)


def update_jobs(source_refresh_job_name, config_name):
    try:
        aps.app.logger.info("Check for job updates started.")

        config_obj = config_by_name[config_name]()

        with aps.app.app_context():
            config_obj.set_pushgateways(aa)

            config_obj.add_jobs_from_source(aa)

        job_list = aps.app.config.get('SCHEDULER_JOBS')

        pushgateways = config_obj.PUSHGATEWAYS

        jobs = {}

        for i in range(len(job_list)):
            job_name = job_list[i]['id']

            if job_name not in config_obj.jobs.keys():
                delete_job(job_name, pushgateways)

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
                    delete_job(job_name, pushgateways)

                    aps.modify_job(**config_obj.SCHEDULER_JOBS[i])

                    aps.app.logger.info("Job '" + job_name + "' updated.")
            else:
                aps.add_job(**config_obj.SCHEDULER_JOBS[i])

                aps.app.logger.info("Job '" + job_name + "' added.")

            if run_job:
                aps.run_job(job_name)

        aps.app.config.from_object(config_obj)

        aps.app.logger.info("Check for job updates completed.")
    except Exception as e:
        aps.app.logger.warning("Check for job updates failed. " + type(e).__name__ + ": " + str(e))

        aps.pause_job(source_refresh_job_name)


class JobCollector:
    instance = None

    def __init__(self, job_name):
        self._job_name = job_name

    def collect(self):
        pushgateways = aps.app.config.get('PUSHGATEWAYS')

        for metric_name, info in job_collector_metrics[self._job_name].items():
            json_label_data = list(info.keys())[0]

            label_dict = json.loads(json_label_data)

            g = GaugeMetricFamily(metric_name, '', labels=label_dict.keys())

            if self.instance is None:
                if 'instance' in label_dict.keys():
                    self.instance = label_dict.pop('instance')
                else:
                    self.instance = ''

            for json_label_data, metric in info.items():
                label_dict = json.loads(json_label_data)

                options = {}

                if len(pushgateways) == 0:
                    options['timestamp'] = metric[1]

                g.add_metric(label_dict.values(), metric[0], **options)

            yield g
