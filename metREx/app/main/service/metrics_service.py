import json
import re
import traceback

from collections import OrderedDict

from datetime import datetime, timezone

import inflect
import numpy
import pytz

from ..api.appd import AppD
from ..api.extrahop import ExtraHop
from ..api.newrelic import NewRelic
from ..database import DatabaseAccessLayer

from ...main import *
from ..util.multiprocessing_helper import *


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
    label = re.sub(r'\W', '', label)
    label = re.sub(r'_{2,}', '_', label)

    return label.lower()


def format_metric(string):
    metric = re.sub(r'(?<=\S)(/sec)', ' per sec', string)
    metric = re.sub(r'[ \-]', '_', metric)
    metric = re.sub(r'\W', '', metric)
    metric = re.sub(r'_{2,}', '_', metric)

    return metric.lower()


def get_metrics(func, job_name, args, push_services, conn=None):
    collector_metrics = func(*args)

    if conn is not None:
        conn.send(collector_metrics)

    aps.app.logger.info("Fetched metrics for job '" + job_name + "'.")

    set_job_collector_metrics(job_name, collector_metrics, push_services)

    for vendor, services in push_services.items():
        globals()['push_' + vendor + '_job_metrics'](job_name, services)


def get_metric_info(service):
    service_name_pattern = re.compile(r'\[(?P<instance>[^\[\]]+)\]', re.X)

    prefix = re.sub(service_name_pattern, '', service)

    instance = None

    m = service_name_pattern.search(service)

    if m is not None:
        components = m.groupdict()

        instance = components['instance']

    return prefix.lower(), instance


def is_element_in_iterable_no_case(element, iterable):
    return element.lower() in [val.lower() for val in list(iterable)]


def is_number(n):
    try:
        float(n)
    except ValueError:
        return False

    return True


def make_label_singular(label):
    p = inflect.engine()

    words = label.split('_')

    words.append(p.singular_noun(words.pop()))

    return '_'.join(words)


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
    def _get_appdynamics_metrics(job_name, service_names, application, metric_path, minutes, static_labels=()):
        collector_metrics = {}

        with aps.app.app_context():
            all_labels = []

            metric_data = {}

            for service_name in service_names['source']:
                prefix, instance = get_metric_info(service_name)

                dal = AppD(aa)
                dal.init_aa(service_name)

                aps.app.logger.info("Initialized connection for job '" + job_name + "' to AppDynamics service '" + service_name + "'.")

                if not application and dal.application is not None:
                    application = dal.application

                tiers = []
                nodes = []

                if application != 'Database Monitoring':
                    result = dal.client.get_tiers(application)

                    for tier_obj in result:
                        tiers.append(tier_obj.name)

                    result = dal.client.get_nodes(application)

                    for node_obj in result:
                        nodes.append(node_obj.name)

                options = {
                    'time_range_type': 'BEFORE_NOW',
                    'duration_in_mins': minutes,
                    'rollup': True
                }

                result = dal.client.get_metrics(metric_path, application, **options)

                metrics = []

                for metric_obj in result:
                    if metric_obj.values:
                        components = metric_obj.path.split('|')

                        if components is not None:
                            metric_profile = [
                                format_label(components.pop(0)),
                                format_label(components.pop())
                            ]

                            label_dict = OrderedDict([
                                ('application', application)
                            ])

                            if service_names['push'] or aps.app.config['DEFAULT_PUSH_SERVICE_NAMES']:
                                if instance is not None:
                                    label_dict['instance'] = instance

                            if application == 'Database Monitoring':
                                label = make_label_singular(metric_profile[0])

                                label_dict[label] = components.pop(0)

                                if ':' in components[0]:
                                    label_dict['node'] = components.pop(0)

                                for component in components:
                                    metric_profile.insert(len(metric_profile)-1, format_label(component))
                            else:
                                if metric_profile[0] == 'application_infrastructure_performance':
                                    i = 1

                                    while i < len(components):
                                        if components[i] != 'Individual Nodes' and components[i] not in nodes:
                                            metric_profile.insert(len(metric_profile)-1, format_label(components[i]))

                                            if components[i-1] == 'JVM':
                                                if components[i] == 'Garbage Collection':
                                                    label = make_label_singular(format_label(components.pop(i+1)))

                                                    label_dict[label] = components.pop(i+1)
                                                elif components[i] == 'Memory':
                                                    label = format_label(components[i])

                                                    label_dict[label] = components.pop(i+1)

                                        i += 1
                                else:
                                    if metric_profile[0] == 'business_transaction_performance':
                                        label = make_label_singular(format_label(components.pop(0)))

                                        if label == 'business_transaction_group':
                                            label_dict[label] = components.pop(0)
                                        elif label == 'business_transaction':
                                            label_dict[label] = components.pop(1)
                                    elif metric_profile[0] in ['errors', 'information_points', 'service_endpoints']:
                                        label = make_label_singular(metric_profile[0])

                                        label_dict[label] = components.pop(1)

                                    external_calls_index = 0

                                    while len(components) > 0:
                                        if components[0] in tiers:
                                            label_dict['tier'] = components.pop(0)
                                        else:
                                            pattern = re.compile(r'^(?P<desc>Discovered backend call) - (?P<entity>.+)$')

                                            m = pattern.match(components[0])

                                            if m is not None:
                                                subcomponents = m.groupdict()

                                                label = format_label(subcomponents['desc'])

                                                label_dict[label] = subcomponents['entity']

                                                components.pop(0)
                                            else:
                                                label = make_label_singular(format_label(components.pop(0)))

                                                if label == 'external_call':
                                                    external_calls_index += 1

                                                    label_base = '%s_%d' % (label, external_calls_index)

                                                    pattern = re.compile(r'^Call-(?P<type>\S+) to (?P<target>.+)$')

                                                    m = pattern.match(components.pop(0))

                                                    if m is not None:
                                                        subcomponents = m.groupdict()

                                                        label_dict[label_base] = subcomponents['type']

                                                        pattern = re.compile(r'^(?P<desc>Discovered backend call) - (?P<entity>.+)$')

                                                        m = pattern.match(subcomponents['target'])

                                                        if m is not None:
                                                            subcomponents = m.groupdict()

                                                            label = '%s_%s' % (label_base, format_label(subcomponents['desc']))

                                                            label_dict[label] = subcomponents['entity']
                                                        else:
                                                            label = '%s_tier' % label_base

                                                            label_dict[label] = subcomponents['target']

                                                            if len(components) > 0:
                                                                components.pop(0)
                                                elif label == 'incoming_cross_app_call':
                                                    label_base = label

                                                    label = '%s_application' % label_base

                                                    label_dict[label] = components.pop(0)

                                                    pattern = re.compile(r'^Call-(?P<type>\S+) from (?P<source>.+)$')

                                                    m = pattern.match(components.pop(0))

                                                    if m is not None:
                                                        subcomponents = m.groupdict()

                                                        label_dict[label_base] = subcomponents['type']

                                                        label = '%s_tier' % label_base

                                                        label_dict[label] = subcomponents['source']
                                                elif label in ['individual_node', 'thread_task']:
                                                    label_dict[label] = components.pop(0)

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

                            for label in label_dict.keys():
                                if label not in all_labels:
                                    all_labels.append(label)

                            timestamp = row['start_time_ms'] / 1000 + (int(minutes) * 60)

                            for metric in metrics:
                                metric_name = '%s.%s.%s' % (prefix, '.'.join(metric_profile), metric)

                                if metric_name not in metric_data.keys():
                                    metric_data[metric_name] = []

                                metric_data[metric_name].append((
                                    label_dict,
                                    int(metric_dict[metric]),
                                    timestamp
                                ))

            for metric_name, data in metric_data.items():
                for (label_dict, value, timestamp) in data:
                    normalized_label_dict = OrderedDict()

                    for label in all_labels:
                        if label in label_dict.keys():
                            normalized_label_dict[label] = label_dict[label]
                        else:
                            normalized_label_dict[label] = ''

                    json_label_data = json.dumps(normalized_label_dict)

                    if metric_name not in collector_metrics.keys():
                        collector_metrics[metric_name] = {}

                    if json_label_data not in collector_metrics[metric_name].keys():
                        collector_metrics[metric_name][json_label_data] = (value, timestamp)

        return collector_metrics

    @staticmethod
    def _get_database_metrics(job_name, service_names, statement, value_columns, static_labels=(), timestamp_column=None, timezones={}):
        def is_value_column(column):
            return is_element_in_iterable_no_case(column, value_columns)

        collector_metrics = {}

        with aps.app.app_context():
            for service_name in service_names['source']:
                prefix, instance = get_metric_info(service_name)

                dal = DatabaseAccessLayer(db)
                dal.init_db(service_name)

                aps.app.logger.info("Initialized connection for job '" + job_name + "' to database service '" + service_name + "'.")

                result = dal.execute(statement)

                timestamp = datetime.now(timezone.utc).timestamp()

                db_tzinfo = None

                if timestamp_column is not None and service_name in timezones.keys():
                    db_tzinfo = pytz.timezone(timezones[service_name])

                normalized_value_columns = None
                normalized_timestamp_column = None

                for row in result:
                    def is_unmatched_value_column(column):
                        return not is_element_in_iterable_no_case(column, row.keys())

                    if normalized_value_columns is None:
                        normalized_value_columns = list(filter(is_value_column, row.keys()))

                        unmatched_value_columns = list(filter(is_unmatched_value_column, value_columns))

                        if unmatched_value_columns:
                            raise ValueError("Value column(s) " + ", ".join(["'" + column + "'" for column in unmatched_value_columns]) + " specified in job '" + job_name + "' not returned in query result.")

                    if timestamp_column is not None and normalized_timestamp_column is None:
                        for column in row.keys():
                            if timestamp_column.lower() == column.lower():
                                normalized_timestamp_column = column

                        if normalized_timestamp_column is None:
                            raise ValueError("Timestamp column '" + timestamp_column + "' specified in job '" + job_name + "' not returned in query result.")

                    label_dict = OrderedDict()

                    if service_names['push'] or aps.app.config['DEFAULT_PUSH_SERVICE_NAMES']:
                        if instance is not None:
                            label_dict['instance'] = instance

                    label_dict.update(OrderedDict([
                        (format_label(column), to_string(row[column])) for column in row.keys() if column not in normalized_value_columns and column != normalized_timestamp_column
                    ]))

                    label_dict.update(OrderedDict([
                        (format_label(label), value) for label, value in static_labels if format_label(label) not in label_dict.keys()
                    ]))

                    if db_tzinfo is not None:
                        if isinstance(row[normalized_timestamp_column], datetime):
                            if row[normalized_timestamp_column].tzinfo is not None and row[normalized_timestamp_column].tzinfo.utcoffset(row[normalized_timestamp_column]) is not None:
                                timestamp = row[normalized_timestamp_column].timestamp()
                            else:
                                timestamp = row[normalized_timestamp_column].astimezone(db_tzinfo).timestamp()

                    json_label_data = json.dumps(label_dict)

                    for column in normalized_value_columns:
                        metric_name = '%s.%s' % (prefix, format_metric(column))

                        if metric_name not in collector_metrics.keys():
                            collector_metrics[metric_name] = {}

                        if json_label_data not in collector_metrics[metric_name].keys():
                            collector_metrics[metric_name][json_label_data] = (row[column], timestamp)

        return collector_metrics

    @staticmethod
    def _get_extrahop_metrics(job_name, service_names, params, metric, aggregation, minutes, static_labels=()):
        collector_metrics = {}

        aggregation = test_aggregation_settings(aggregation, job_name)

        with aps.app.app_context():
            for service_name in service_names['source']:
                prefix, instance = get_metric_info(service_name)

                dal = ExtraHop(aa)
                dal.init_aa(service_name)

                aps.app.logger.info("Initialized connection for job '" + job_name + "' to ExtraHop service '" + service_name + "'.")

                options = {**params, **{
                    'from': '-%dm' % minutes,
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

                        if service_names['push'] or aps.app.config['DEFAULT_PUSH_SERVICE_NAMES']:
                            if instance is not None:
                                label_dict['instance'] = instance

                        label_dict.update(OrderedDict([
                            (format_label(label), value) for label, value in static_labels if format_label(label) not in label_dict.keys()
                        ]))

                        json_label_data = json.dumps(label_dict)

                        for func in aggregation['funcs']:
                            metric_name = '%s.%s.%s' % (prefix, format_metric(metric), func.lower())

                            if metric_name not in collector_metrics.keys():
                                collector_metrics[metric_name] = {}

                            if json_label_data not in collector_metrics[metric_name].keys():
                                collector_metrics[metric_name][json_label_data] = (aggregate_values_by_func(func, values), timestamp)

        return collector_metrics

    @staticmethod
    def _get_newrelic_metrics(job_name, service_names, account_id, statement, value_attrs, minutes, static_labels=()):
        def is_value_attr(attr):
            return is_element_in_iterable_no_case(attr, value_attrs)

        collector_metrics = {}

        with aps.app.app_context():
            nrql_query = re.sub(r'[\r\n]+', ' ', statement)

            for service_name in service_names['source']:
                prefix, instance = get_metric_info(service_name)

                dal = NewRelic(aa)
                dal.init_aa(service_name)

                aps.app.logger.info("Initialized connection for job '" + job_name + "' to New Relic service '" + service_name + "'.")

                account_id = account_id or dal.account_id

                query_str = """{
                   actor {
                      account(id: %d) {
                         nrql(query: "%s SINCE %d minutes AGO") {
                            results
                         }
                      }
                   }
                }""" % (account_id, nrql_query, minutes)

                result = dal.client.query(query_str)

                timestamp = datetime.now(timezone.utc).timestamp()

                if 'data' in result.keys():
                    if result['data']['actor']['account']['nrql']['results']:
                        normalized_value_attrs = None

                        for row in result['data']['actor']['account']['nrql']['results']:
                            def is_unmatched_value_attr(attr):
                                return not is_element_in_iterable_no_case(attr, row.keys())

                            if normalized_value_attrs is None:
                                normalized_value_attrs = list(filter(is_value_attr, row.keys()))

                                unmatched_value_attrs = list(filter(is_unmatched_value_attr, value_attrs))

                                if unmatched_value_attrs:
                                    raise ValueError("Value attribute(s) " + ", ".join(["'" + attr + "'" for attr in unmatched_value_attrs]) + " specified in job '" + job_name + "' not returned in query result.")

                            label_dict = OrderedDict()

                            if service_names['push'] or aps.app.config['DEFAULT_PUSH_SERVICE_NAMES']:
                                if instance is not None:
                                    label_dict['instance'] = instance

                            label_dict.update(OrderedDict([
                                (format_label(attr), to_string(row[attr])) for attr in row.keys() if attr not in normalized_value_attrs
                            ]))

                            label_dict.update(OrderedDict([
                                (format_label(label), value) for label, value in static_labels if format_label(label) not in label_dict.keys()
                            ]))

                            json_label_data = json.dumps(label_dict)

                            for attr in normalized_value_attrs:
                                metric_name = '%s.%s' % (prefix, format_metric(attr))

                                if metric_name not in collector_metrics.keys():
                                    collector_metrics[metric_name] = {}

                                if json_label_data not in collector_metrics[metric_name].keys():
                                    collector_metrics[metric_name][json_label_data] = (row[attr], timestamp)

        return collector_metrics

    @staticmethod
    def generate_metrics(*args):
        category = args[0]
        job_name = args[1]
        service_names = args[2]

        job = aps.get_job(job_name)

        func_name = '_get_' + category + '_metrics'

        if hasattr(Metrics, func_name):
            func = getattr(Metrics, func_name)

            with aps.app.app_context():
                try:
                    with JOB_EXECUTION_TIME.labels(job_name, category).time():
                        push_services = get_push_services(
                            job_name,
                            (aps.app.config['DEFAULT_PUSH_SERVICE_NAMES'] + service_names['push'])
                        )

                        enforce_timeout = aps.app.config['LIMIT_JOB_EXECUTION_TIME'] and job.next_run_time is not None

                        if enforce_timeout:
                            # Prevent database jobs with JDBC connections from running under multiprocessing
                            if category == 'database':
                                for service_name in service_names['source']:
                                    if service_name in aps.app.config['SQLALCHEMY_BINDS'].keys():
                                        bind = aps.app.config['SQLALCHEMY_BINDS'][service_name]

                                        result = re.search(r'jdbc', bind)

                                        enforce_timeout = result is None
                                        break

                        if enforce_timeout:
                            pconn, cconn = ctx.Pipe()

                            p = Process(
                                target=get_metrics,
                                args=(func, job_name, args[1:], push_services, cconn)
                            )

                            end_dt = job.next_run_time
                            job_tz = pytz.timezone(end_dt.tzname())

                            p.start()

                            max_execution_time = (end_dt - datetime.now(job_tz)).total_seconds() - 1

                            p.join(timeout=max_execution_time)

                            if pconn.poll():
                                collector_metrics = pconn.recv()

                                set_job_collector_metrics(job_name, collector_metrics, push_services)

                            pconn.close()
                            cconn.close()

                            if p.is_alive():
                                p.kill()

                                raise TimeoutWarning("Process timed out.")

                            if p.exception is not None:
                                raise p.exception
                        else:
                            get_metrics(func, job_name, args[1:], push_services)
                except Exception as e:
                    exception = e.__class__.__name__

                    JOB_FAILURES.labels(job_name, category, exception).inc()

                    aps.app.logger.warning("Job '" + job_name + "' failed. " + exception + ": " + str(e))
                    aps.app.logger.debug(traceback.format_exc())

                    if aps.app.config['SUSPEND_JOB_ON_FAILURE']:
                        aps.pause_job(job_name)

                        aps.app.logger.warning("Job '" + job_name + "' suspended.")

                    unset_job_collector_metrics(job_name)

    @staticmethod
    def read_prometheus_metrics(name):
        registry = get_registry(name)

        return generate_latest(registry)
