import json
import numpy
import re

from collections import OrderedDict

from datetime import datetime, timezone
import pytz

from prometheus_client import generate_latest

from ..api.appd import AppD
from ..api.extrahop import ExtraHop
from ..database import DatabaseAccessLayer

from ...main import db, aa, aps, set_job_collector_metrics, get_registry, unregister_collector, registered_collectors


def aggregate_values_by_func(func, values):
    if is_number(func):
        value = numpy.percentile(values, int(func))
    else:
        value = 0

        if func == 'avg':
            if values:
                value = numpy.average(values)
        elif func == 'count':
            value = len(values)
        elif func == 'min':
            value = numpy.min(values)
        elif func == 'max':
            value = numpy.max(values)
        elif func == 'sum':
            value = numpy.sum(values)

    return value


def format_label(string):
    label = re.sub(r'[().\'\"]|((?<![/:])/)', '', string)
    label = re.sub(r'^%(?=\w)', 'percent ', label)
    label = re.sub(r'%', ' percent', label)
    label = re.sub(r'>', 'greater than', label)
    label = re.sub(r'<', 'less than', label)
    label = re.sub(r'SQL\*Net', 'Net8', label)
    label = re.sub(r'[ \-]', '_', label)

    return label.lower()


def get_metric_info(service):
    service_name_pattern = re.compile(r'\[(?P<instance>[^\[\]]+)\]', re.X)

    prefix = re.sub(service_name_pattern, '', service)

    instance = None

    m = service_name_pattern.search(service)

    if m is not None:
        components = m.groupdict()

        instance = components['instance']

    return prefix.lower(), instance


def is_number(n):
    try:
        float(n)
    except ValueError:
        return False

    return True


def test_aggregation_match(value, aggregation):
    if 'threshold' in aggregation.keys():
        return eval('%d %s %d' % (value, aggregation['threshold']['operator'], int(aggregation['threshold']['value'])))

    return True


def test_aggregation_settings(aggregation, job_name):
    if 'funcs' in aggregation.keys():
        valid_funcs = [
            'avg',
            'count',
            'min',
            'max',
            'sum'
        ]

        for func in aggregation['funcs']:
            if func not in valid_funcs:
                if is_number(func):
                    if int(func) not in range(0, 101):
                        raise ValueError("Invalid aggregation percentile '" + func + "' in job '" + job_name + "'.")
                else:
                    raise ValueError("Unsupported aggregation function '" + func + "' in job '" + job_name + "'.")
    else:
        aggregation['funcs'] = [
            'count'
        ]

    if 'threshold' in aggregation.keys():
        if 'operator' in aggregation['threshold'].keys():
            valid_operator = [
                '>',
                '<',
                '>=',
                '<=',
                '=',
                '<>',
                '!='
            ]

            if aggregation['threshold']['operator'] not in valid_operator:
                raise ValueError("Unsupported aggregation threshold operator '" + aggregation['threshold']['operator'] + "' in job '" + job_name + "'.")
        else:
            raise ValueError("No operator specified for aggregation threshold in job '" + job_name + "'.")

        if 'value' in aggregation['threshold'].keys():
            if is_number(aggregation['threshold']['value']):
                aggregation['threshold']['value'] = aggregation['threshold']['value']
            else:
                raise ValueError("Invalid value '" + aggregation['threshold']['value'] + "' specified for aggregation threshold in job '" + job_name + "'.")
        else:
            raise ValueError("No value specified for aggregation threshold in job '" + job_name + "'.")

    return aggregation


def to_string(n):
    return str(n) if n is not None else ''


class Metrics:
    @staticmethod
    def _get_appdynamics_metrics(job_name, services, application, metric_path, minutes, static_labels=()):
        collector_metrics = {}

        pushgateways = aps.app.config.get('PUSHGATEWAYS')

        for service_name in services:
            prefix, instance = get_metric_info(service_name)

            dal = AppD(aa)
            dal.init_aa(service_name)

            options = {
                'time_range_type': 'BEFORE_NOW',
                'duration_in_mins': int(minutes),
                'rollup': True
            }

            result = dal.client.get_metrics(metric_path, application, **options)

            metrics = []

            for metric_obj in result:
                components = metric_obj.path.split('|')

                if components is not None:
                    label_dict = OrderedDict()

                    if len(pushgateways):
                        if instance is not None:
                            label_dict['instance'] = instance

                    if application == 'Database Monitoring':
                        label_dict['collector'] = components.pop(1)

                        while len(components) > 3:
                            node = format_label(components.pop(1))

                            label_dict[node] = components.pop(1)
                    else:
                        label_dict['application'] = application

                        if components[0] == 'Backends':
                            pattern = re.compile(r'^(?P<node>Discovered backend call) - (?P<value>.+)$', re.X)

                            m = pattern.match(components.pop(1))

                            if m is not None:
                                subcomponents = m.groupdict()

                                node = format_label(subcomponents['node'])

                                label_dict[node] = subcomponents['value']
                        elif components[0] == 'Service Endpoints':
                            label_dict['tier'] = components.pop(1)
                            label_dict['service_endpoint'] = components.pop(1)

                            if components[1] == 'Individual Nodes':
                                node = format_label(components.pop(1))

                                label_dict[node] = components.pop(1)
                        elif components[0] == 'Overall Application Performance':
                            if len(components) > 2:
                                label_dict['tier'] = components.pop(1)

                                if components[1] == 'Individual Nodes':
                                    node = format_label(components.pop(1))

                                    label_dict[node] = components.pop(1)

                                while len(components) > 3:
                                    if components[1] == 'External Calls':
                                        pattern = re.compile(r'^(?P<node>.+)(?= to Discovered) to Discovered backend call - (?P<value>.+)$', re.X)

                                        m = pattern.match(components.pop(2))

                                        if m is not None:
                                            subcomponents = m.groupdict()

                                            node = format_label(subcomponents['node'])

                                            label_dict[node] = subcomponents['value']
                                            break
                                    else:
                                        node = format_label(components.pop(1))

                                        label_dict[node] = components.pop(1)
                        elif components[0] == 'Business Transaction Performance':
                            if components[1] == 'Business Transaction Groups':
                                node = format_label(components.pop(1))

                                label_dict[node] = components.pop(1)
                            elif components[1] == 'Business Transactions':
                                node = format_label(components.pop(1))

                                label_dict['tier'] = components.pop(1)
                                label_dict[node] = components.pop(1)

                                if components[1] == 'Individual Nodes':
                                    node = format_label(components.pop(1))

                                    label_dict[node] = components.pop(1)

                                while len(components) > 3:
                                    if components[1] == 'External Calls':
                                        pattern = re.compile(r'^(?P<node>.+)(?= to Discovered) to Discovered backend call - (?P<value>.+)$', re.X)

                                        m = pattern.match(components.pop(2))

                                        if m is not None:
                                            subcomponents = m.groupdict()

                                            node = format_label(subcomponents['node'])

                                            label_dict[node] = subcomponents['value']
                                            break
                                    else:
                                        node = format_label(components.pop(1))

                                        label_dict[node] = components.pop(1)
                        elif components[0] == 'Application Infrastructure Performance':
                            label_dict['tier'] = components.pop(1)

                            if components[1] == 'Individual Nodes':
                                node = format_label(components.pop(1))

                                label_dict[node] = components.pop(1)

                            while len(components) > 3:
                                node = format_label(components.pop(1))

                                label_dict[node] = components.pop(1)
                        else:
                            break

                    metric_profile = '_'.join([
                        format_label(component) for component in components
                    ])

                    if metric_obj.values:
                        row = metric_obj.values[0].__dict__

                        metric_dict = OrderedDict([
                            (key, value) for key, value in row.items() if key != 'start_time_ms'
                        ])

                        if not metrics:
                            metrics = [
                                metric for metric, value in metric_dict.items() if is_number(value)
                            ]

                        label_dict.update(OrderedDict([
                            (format_label(label), value) for label, value in static_labels if format_label(label) not in label_dict.keys()
                        ]))

                        timestamp = row['start_time_ms'] / 1000 + (int(minutes) * 60)

                        json_label_data = json.dumps(label_dict)

                        for metric in metrics:
                            metric_name = prefix + '_' + metric_profile + '_' + metric.lower()

                            if metric_name not in collector_metrics.keys():
                                collector_metrics[metric_name] = {}

                            if json_label_data not in collector_metrics[metric_name]:
                                collector_metrics[metric_name][json_label_data] = (int(metric_dict[metric]), timestamp)

        return collector_metrics

    @staticmethod
    def _get_database_metrics(job_name, services, statement, value_columns, static_labels=(), timestamp_column=None, timezones={}):
        collector_metrics = {}

        pushgateways = aps.app.config.get('PUSHGATEWAYS')

        for service_name in services:
            prefix, instance = get_metric_info(service_name)

            dal = DatabaseAccessLayer(db)
            dal.init_db(service_name)

            result = dal.execute(statement)

            timestamp = datetime.now(timezone.utc).timestamp()

            db_tzinfo = None

            if timestamp_column is not None and service_name in timezones.keys():
                db_tzinfo = pytz.timezone(timezones[service_name])

            for row in result:
                label_dict = OrderedDict()

                if len(pushgateways):
                    if instance is not None:
                        label_dict['instance'] = instance

                label_dict.update(OrderedDict([
                    (format_label(column), to_string(row[column])) for column in row.keys() if column not in value_columns and column != timestamp_column
                ]))

                label_dict.update(OrderedDict([
                    (format_label(label), value) for label, value in static_labels if format_label(label) not in label_dict.keys()
                ]))

                if db_tzinfo is not None and timestamp_column in row.keys():
                    if isinstance(row[timestamp_column], datetime):
                        if row[timestamp_column].tzinfo is not None and row[timestamp_column].tzinfo.utcoffset(row[timestamp_column]) is not None:
                            timestamp = row[timestamp_column].timestamp()
                        else:
                            timestamp = row[timestamp_column].astimezone(db_tzinfo).timestamp()

                json_label_data = json.dumps(label_dict)

                for column in value_columns:
                    metric_name = prefix + '_' + column.lower()

                    if metric_name not in collector_metrics.keys():
                        collector_metrics[metric_name] = {}

                    if json_label_data not in collector_metrics[metric_name]:
                        collector_metrics[metric_name][json_label_data] = (row[column], timestamp)

        return collector_metrics

    @staticmethod
    def _get_extrahop_metrics(job_name, services, params, metric, aggregation, minutes, static_labels=()):
        collector_metrics = {}

        pushgateways = aps.app.config.get('PUSHGATEWAYS')

        for service_name in services:
            prefix, instance = get_metric_info(service_name)

            aggregation = test_aggregation_settings(aggregation, job_name)

            dal = ExtraHop(aa)
            dal.init_aa(service_name)

            options = {**params, **{
                'from': '-%sm' % minutes,
                'until': 0
            }}

            result = dal.client.get_metrics(**options)

            timestamp = datetime.now(timezone.utc).timestamp()

            if 'stats' in result.keys():
                metric_dict = OrderedDict()

                for row in result['stats']:
                    if row['values']:
                        if row['values'][0]:
                            metric_spec_name = row['values'][0][0]['key']['str']

                            if metric_spec_name not in metric_dict.keys():
                                metric_dict[metric_spec_name] = []

                            value = int(row['values'][0][0]['value'])

                            if test_aggregation_match(value, aggregation):
                                metric_dict[metric_spec_name].append(value)

                for metric_spec_name, values in metric_dict.items():
                    label_dict = OrderedDict([
                        ('metric_spec_name', metric_spec_name.lower())
                    ])

                    if len(pushgateways):
                        if instance is not None:
                            label_dict['instance'] = instance

                    label_dict.update(OrderedDict([
                        (format_label(label), value) for label, value in static_labels if format_label(label) not in label_dict.keys()
                    ]))

                    json_label_data = json.dumps(label_dict)

                    for func in aggregation['funcs']:
                        metric_name = prefix + '_' + metric.lower() + '_' + func.lower()

                        if metric_name not in collector_metrics.keys():
                            collector_metrics[metric_name] = {}

                        if json_label_data not in collector_metrics[metric_name]:
                            collector_metrics[metric_name][json_label_data] = (aggregate_values_by_func(func, values), timestamp)

        return collector_metrics

    @staticmethod
    def generate_metrics(*args):
        if len(args) >= 2:
            category = args[0]
            job_name = args[1]

            func_name = '_get_' + category + '_metrics'

            if hasattr(Metrics, func_name):
                with aps.app.app_context():
                    try:
                        aps.app.logger.info("Job '" + job_name + "' started.")

                        func = getattr(Metrics, func_name)
                        collector_metrics = func(*args[1:])

                        set_job_collector_metrics(job_name, collector_metrics)

                        aps.app.logger.info("Job '" + job_name + "' completed.")
                    except Exception as e:
                        aps.app.logger.warning("Job '" + job_name + "' failed. " + type(e).__name__ + ": " + str(e))

                        if aps.app.config.get('SUSPEND_JOB_ON_FAILURE'):
                            aps.pause_job(job_name)

                            aps.app.logger.warning("Job '" + job_name + "' suspended.")

                        if job_name in registered_collectors.keys():
                            unregister_collector(job_name, registered_collectors[job_name])

                            del registered_collectors[job_name]

    @staticmethod
    def read_prometheus_metrics(job_name):
        registry = get_registry(job_name)

        return generate_latest(registry)
