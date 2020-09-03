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

    service_name_pattern = re.compile(r'^' + r'(?:(?:' + re.escape(apialchemy_prefix) + r')|(?:' + re.escape(sqlalchemy_prefix) + r'))(?P<name>.+)$', re.X)

    for job_name, credentials in jobs.items():
        if 'services' in credentials.keys() and 'interval_minutes' in credentials.keys():
            service_names = {}

            for service in credentials['services']:
                m = service_name_pattern.match(service)

                if m is not None:
                    components = m.groupdict()

                    service_names[service] = components['name']
                else:
                    raise ValueError("Invalid service name: '" + service + "'.")

            for k, v in credentials.items():
                if isinstance(v, str):
                    undefined_env_vars, credentials[k] = populate_env_vars(v)

                    if undefined_env_vars:
                        raise ValueError("Job '" + job_name + "' references undefined environment variable(s): " + ", ".join(undefined_env_vars) + ".")

            valid_service_names = list(apialchemy_binds.keys()) + list(sqlalchemy_binds.keys())

            for service, name in service_names.items():
                if name not in valid_service_names:
                    raise ValueError("Service '" + service + "' not found for job '" + job_name + "'.")

            if all(service_name in apialchemy_binds.keys() and 'vendor' in apialchemy_binds[service_name].keys() for service_name in service_names.values()):
                vendor = None

                for service_name in service_names.values():
                    if vendor is None:
                        vendor = apialchemy_binds[service_name]['vendor']

                    if apialchemy_binds[service_name]['vendor'] != vendor:
                        raise ValueError("Services defined for job '" + job_name + "' must reference same API vendor.")

                job_args = [
                    vendor,
                    job_name,
                    list(service_names.values()),
                    int(credentials['interval_minutes']) * 60
                ]

                service_job_args = None

                if vendor == 'appdynamics':
                    if 'application' in credentials.keys():
                        job_args.append(credentials['application'])

                        if 'metric_path' in credentials.keys():
                            service_job_args = [
                                credentials['metric_path'],
                                credentials['interval_minutes']
                            ]
                elif vendor == 'extrahop':
                    if 'metric_params' in credentials.keys() and 'metric_name' in credentials.keys() and 'aggregation' in credentials.keys():
                        service_job_args = [
                            credentials['metric_params'],
                            credentials['metric_name'],
                            credentials['aggregation'],
                            credentials['interval_minutes']
                        ]

                if service_job_args is not None:
                    job_args += service_job_args

                    if 'static_labels' in credentials.keys():
                        static_label_list = list(filter(None, re.split(r'\s*,\s*', credentials['static_labels'])))

                        job_args.append([
                            tuple(filter(None, label_str.split(':'))) for label_str in static_label_list
                        ])

                    job_list.append(build_job(*job_args))

                    continue
            elif all(service_name in sqlalchemy_binds.keys() for service_name in service_names.values()):
                if 'statement' in credentials.keys() and 'value_columns' in credentials.keys():
                    job_args = [
                        'database',
                        job_name,
                        list(service_names.values()),
                        int(credentials['interval_minutes']) * 60,
                        credentials['statement'],
                        list(filter(None, re.split(r'\s*,\s*', credentials['value_columns'])))
                    ]

                    if 'static_labels' in credentials.keys():
                        static_label_list = list(filter(None, re.split(r'\s*,\s*', credentials['static_labels'])))

                        job_args.append([
                            tuple(filter(None, label_str.split(':'))) for label_str in static_label_list
                        ])

                    if 'timestamp_column' in credentials.keys():
                        job_args.append(credentials['timestamp_column'])

                        timezones = {service_name: sqlalchemy_binds[service_name]['timezone'] if 'timezone' in sqlalchemy_binds[service_name].keys() else db_default_local_tz for service_name in service_names.values()}

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

    api_vendor_pattern = re.compile(r'^(?:(?P<vendor>\w+)(?:\+(?:http|https))?)(?=://)', re.X)

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

                                contents = dal.service.get_file_contents(dal.client,
                                                                         jobs_source_org,
                                                                         jobs_source_repo,
                                                                         jobs_source_path,
                                                                         jobs_source_branch)

                                jobs = get_services_from_yaml(yaml.safe_load(contents))

                                jobs_source_templates_path = os.getenv('JOBS_SOURCE_TEMPLATES_PATH')

                                if jobs_source_templates_path is not None:
                                    contents = dal.service.get_file_contents(dal.client,
                                                                             jobs_source_org,
                                                                             jobs_source_repo,
                                                                             jobs_source_templates_path,
                                                                             jobs_source_branch)

                                    templates = get_services_from_yaml(yaml.safe_load(contents))

                                    jobs = apply_job_templates(jobs, templates)
                        else:
                            raise ValueError("Missing environment variable(s) required for jobs source service '" + jobs_source_service + "'.")
            else:
                raise ValueError("Service '" + jobs_source_service + "' not found.")

    return jobs


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
