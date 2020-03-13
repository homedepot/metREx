from flask_restx import Namespace


class MetricsDto:
    api = Namespace('metrics', description='Prometheus metrics')


class SchedulerDto:
    api = Namespace('scheduler', description='Flask-APScheduler API')
