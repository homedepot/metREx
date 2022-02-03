import os
import re
import yaml

import pytz

package_components = __package__.split('.')

package_components.pop()

job_func_root = '.'.join(package_components)


def apply_job_templates(jobs, templates):
    for job_name, credentials in jobs.items():
        if 'use_template' in credentials.keys():
            template_name = credentials.pop('use_template')

            if template_name in templates.keys():
                template = templates[template_name].copy()

                template.update(credentials)

                jobs[job_name].update(template)
            else:
                raise ValueError("Job '" + job_name + "' references undefined template: " + template_name + ".")

    return jobs


def build_job(category, name, bind, seconds, *args):
    return {
        'func': job_func_root + '.service.metrics_service:Metrics.generate_metrics',
        'trigger': 'interval',
        'args': (category, name, bind) + args,
        'id': name,
        'seconds': seconds
    }


def build_job_list(jobs, apialchemy_info, sqlalchemy_info):
    """Builds list of scheduled jobs to assign to SCHEDULER_JOBS"""
    job_list = []

    db_default_local_tz = os.getenv('DB_DEFAULT_LOCAL_TZ')

    if db_default_local_tz not in pytz.all_timezones:
        db_default_local_tz = 'UTC'

    apialchemy_prefix, apialchemy_binds = apialchemy_info
    sqlalchemy_prefix, sqlalchemy_binds = sqlalchemy_info

    push_service_vendors = [
        'graphite',
        'pushgateway',
        'wavefront'
    ]

    valid_service_names = list(apialchemy_binds.keys()) + list(sqlalchemy_binds.keys())

    service_name_pattern = re.compile(r'^' + r'(?:(?:' + re.escape(apialchemy_prefix) + r')|(?:' + re.escape(sqlalchemy_prefix) + r'))(?P<name>.+)$', re.X)

    for job_name, credentials in jobs.items():
        for k, v in credentials.items():
            if isinstance(v, str):
                undefined_env_vars, credentials[k] = populate_env_vars(v)

                if undefined_env_vars:
                    raise ValueError("Job '" + job_name + "' references undefined environment variable(s): " + ", ".join(undefined_env_vars) + ".")

        if 'services' in credentials.keys() and 'interval_minutes' in credentials.keys():
            service_names = {
                'source': [],
                'push': []
            }

            for service in credentials['services']:
                service_name = get_service_name(job_name, service, service_name_pattern, valid_service_names)

                if service_name in apialchemy_binds.keys():
                    if 'vendor' in apialchemy_binds[service_name].keys():
                        if apialchemy_binds[service_name]['vendor'] in push_service_vendors:
                            raise ValueError("Service '" + service + "' defined for job '" + job_name + "' references push API vendor.")
                    else:
                        raise ValueError("Service '" + service + "' defined for job '" + job_name + "' is missing vendor credential.")
                elif service_name not in sqlalchemy_binds.keys():
                    raise ValueError("Service '" + service + "' defined for job '" + job_name + "' does not match any defined connections.")

                service_names['source'].append(service_name)

            if 'push_services' in credentials.keys():
                for service in credentials['push_services']:
                    service_name = get_service_name(job_name, service, service_name_pattern, valid_service_names)

                    if service_name in apialchemy_binds.keys():
                        if 'vendor' in apialchemy_binds[service_name].keys():
                            if apialchemy_binds[service_name]['vendor'] not in push_service_vendors:
                                raise ValueError("Push service '" + service + "' defined for job '" + job_name + "' references unsupported API vendor.")
                        else:
                            raise ValueError("Push service '" + service + "' defined for job '" + job_name + "' is missing vendor credential.")
                    else:
                        raise ValueError("Push service '" + service + "' defined for job '" + job_name + "' does not match any defined API connections.")

                    service_names['push'].append(service_name)

            if all(service_name in apialchemy_binds.keys() for service_name in service_names['source']):
                vendor = None

                for service_name in service_names['source']:
                    if vendor is None:
                        vendor = apialchemy_binds[service_name]['vendor']

                    if apialchemy_binds[service_name]['vendor'] != vendor:
                        raise ValueError("Services defined for job '" + job_name + "' must reference same API vendor.")

                    if vendor == 'appdynamics':
                        if 'application' not in credentials.keys() and 'application' not in apialchemy_binds[service_name].keys():
                            raise ValueError("Services defined for job '" + job_name + "' must contain 'application' credential if job does not.")
                    elif vendor == 'newrelic':
                        if 'account_id' not in credentials.keys() and 'account_id' not in apialchemy_binds[service_name].keys():
                            raise ValueError("Services defined for job '" + job_name + "' must contain 'account_id' credential if job does not.")

                job_args = [
                    vendor,
                    job_name,
                    service_names,
                    int(credentials['interval_minutes']) * 60
                ]

                service_job_args = None

                if vendor == 'appdynamics':
                    application = None

                    if 'application' in credentials.keys():
                        application = credentials['application']

                    job_args.append(application)

                    if 'metric_path' in credentials.keys():
                        service_job_args = [
                            credentials['metric_path'],
                            int(credentials['interval_minutes'])
                        ]
                elif vendor == 'extrahop':
                    if 'metric_params' in credentials.keys() and 'metric_name' in credentials.keys() and 'aggregation' in credentials.keys():
                        service_job_args = [
                            credentials['metric_params'],
                            credentials['metric_name'],
                            credentials['aggregation'],
                            int(credentials['interval_minutes'])
                        ]
                elif vendor == 'newrelic':
                    account_id = None

                    if 'account_id' in credentials.keys():
                        account_id = int(credentials['account_id'])

                    job_args.append(account_id)

                    if 'statement' in credentials.keys() and 'value_attrs' in credentials.keys():
                        if isinstance(credentials['value_attrs'], str):
                            # For backward-compatibility with older versions, which expected comma-delimited string
                            value_attrs = list(filter(None, re.split(r'\s*,\s*', credentials['value_attrs'])))
                        else:
                            value_attrs = list(credentials['value_attrs'])

                        if not value_attrs:
                            raise ValueError("No value attributes specified for job '" + job_name + "'.")

                        service_job_args = [
                            credentials['statement'],
                            value_attrs,
                            int(credentials['interval_minutes'])
                        ]

                if service_job_args is not None:
                    job_args += service_job_args

                    if 'static_labels' in credentials.keys():
                        if isinstance(credentials['static_labels'], str):
                            # For backward-compatibility with older versions, which expected comma-delimited string of key:value pairs
                            static_label_list = list(filter(None, re.split(r'\s*,\s*', credentials['static_labels'])))

                            static_labels = [
                                tuple(filter(None, label_str.split(':'))) for label_str in static_label_list
                            ]
                        else:
                            static_labels = [
                                (label, value) for label, value in credentials['static_labels'].items()
                            ]

                        job_args.append(static_labels)

                    job_list.append(build_job(*job_args))

                    continue
            elif all(service_name in sqlalchemy_binds.keys() for service_name in service_names['source']):
                if 'statement' in credentials.keys() and 'value_columns' in credentials.keys():
                    if isinstance(credentials['value_columns'], str):
                        # For backward-compatibility with older versions, which expected comma-delimited string
                        value_columns = list(filter(None, re.split(r'\s*,\s*', credentials['value_columns'])))
                    else:
                        value_columns = list(credentials['value_columns'])

                    if not value_columns:
                        raise ValueError("No value columns specified for job '" + job_name + "'.")

                    job_args = [
                        'database',
                        job_name,
                        service_names,
                        int(credentials['interval_minutes']) * 60,
                        credentials['statement'],
                        value_columns
                    ]

                    if 'static_labels' in credentials.keys():
                        if isinstance(credentials['static_labels'], str):
                            # For backward-compatibility with older versions, which expected comma-delimited string of key:value pairs
                            static_label_list = list(filter(None, re.split(r'\s*,\s*', credentials['static_labels'])))

                            static_labels = [
                                tuple(filter(None, label_str.split(':'))) for label_str in static_label_list
                            ]
                        else:
                            static_labels = [
                                (label, value) for label, value in credentials['static_labels'].items()
                            ]

                        job_args.append(static_labels)

                    if 'timestamp_column' in credentials.keys():
                        job_args.append(credentials['timestamp_column'])

                        timezones = {
                            service_name: sqlalchemy_binds[service_name]['timezone'] if 'timezone' in sqlalchemy_binds[service_name].keys() else db_default_local_tz for service_name in service_names['source']
                        }

                        job_args.append(timezones)

                    job_list.append(build_job(*job_args))

                    continue
            else:
                raise ValueError("Services defined for job '" + job_name + "' must reference same connection type.")

        raise ValueError("Missing required credential(s) for job '" + job_name + "'.")

    return job_list


def get_jobs_from_services(job_prefix, template_prefix, services):
    jobs = {}
    templates = {}

    job_name_pattern = re.compile(r'^' + re.escape(job_prefix) + r'(?P<name>.+)$', re.X)
    template_name_pattern = re.compile(r'^' + re.escape(template_prefix) + r'.+$', re.X)

    for service in services:
        m = job_name_pattern.match(service.name)

        if m is not None:
            components = m.groupdict()

            name = components['name']

            jobs[name] = service.credentials
        else:
            m = template_name_pattern.match(service.name)

            if m is not None:
                templates[service.name] = service.credentials

    return apply_job_templates(jobs, templates)


def get_jobs_from_source(aa, apialchemy_info):
    jobs = {}

    apialchemy_prefix, apialchemy_binds = apialchemy_info

    service_name_pattern = re.compile(r'^' + r'(?:' + re.escape(apialchemy_prefix) + r')(?P<name>.+)$', re.X)

    api_vendor_pattern = re.compile(r'^(?:(?P<vendor>\w+)(?:\+(?:http|https|proxy))?)(?=://)', re.X)

    jobs_source_service = os.getenv('JOBS_SOURCE_SERVICE')

    if jobs_source_service is not None:
        m = service_name_pattern.match(jobs_source_service)

        if m is not None:
            components = m.groupdict()

            service_name = components['name']

            if service_name in apialchemy_binds.keys():
                conn_str = apialchemy_binds[service_name]

                m = api_vendor_pattern.match(conn_str)

                if m is not None:
                    components = m.groupdict()

                    if components['vendor'] == 'github':
                        from ..api.github import GitHub

                        jobs_source_org = os.getenv('JOBS_SOURCE_ORG')
                        jobs_source_repo = os.getenv('JOBS_SOURCE_REPO')

                        if jobs_source_org is not None and jobs_source_repo is not None:
                            jobs_source_path = os.getenv('JOBS_SOURCE_PATH')

                            if jobs_source_path is not None:
                                jobs_source_branch = os.getenv('JOBS_SOURCE_BRANCH', 'master')

                                dal = GitHub(aa)
                                dal.init_aa(service_name)

                                contents = dal.service.get_file_contents(
                                    dal.client,
                                    jobs_source_org,
                                    jobs_source_repo,
                                    jobs_source_path,
                                    jobs_source_branch
                                )

                                jobs = get_services_from_yaml(yaml.safe_load(contents))

                                jobs_source_templates_path = os.getenv('JOBS_SOURCE_TEMPLATES_PATH')

                                if jobs_source_templates_path is not None:
                                    contents = dal.service.get_file_contents(
                                        dal.client,
                                        jobs_source_org,
                                        jobs_source_repo,
                                        jobs_source_templates_path,
                                        jobs_source_branch
                                    )

                                    templates = get_services_from_yaml(yaml.safe_load(contents))

                                    jobs = apply_job_templates(jobs, templates)
                        else:
                            raise ValueError("Missing environment variable(s) required for jobs source service '" + jobs_source_service + "'.")
            else:
                raise ValueError("Service '" + jobs_source_service + "' not found.")

    return jobs


def get_service_name(job_name, service, service_name_pattern, valid_service_names):
    m = service_name_pattern.match(service)

    if m is not None:
        components = m.groupdict()

        service_name = components['name']

        if service_name not in valid_service_names:
            raise ValueError("Service '" + service + "' not found for job '" + job_name + "'.")
    else:
        raise ValueError("Invalid service name: '" + service + "'.")

    return service_name


def get_services_from_yaml(yaml_data):
    services = {}

    if isinstance(yaml_data, dict):
        for service, credentials in yaml_data.items():
            if isinstance(credentials, dict):
                services[service] = credentials

    return services


def populate_env_vars(string):
    undefined_env_vars = []

    env_var_pattern = re.compile(r'%%(?P<var>\w+)%%', re.X)

    for m in env_var_pattern.finditer(string):
        components = m.groupdict()

        env_var = os.getenv(components['var'])

        if env_var is None:
            undefined_env_vars.append(components['var'])
        else:
            current_env_var_pattern = re.compile(r'%%' + re.escape(components['var']) + r'%%', re.X)

            string = current_env_var_pattern.sub(env_var, string, 1)

    return undefined_env_vars, string
