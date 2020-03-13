import json
import os
import re

from collections import OrderedDict


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
        'func': 'app.main.service.metrics_service:generate_metrics',
        'trigger': 'interval',
        'args': (category, name, bind) + args,
        'id': name,
        'seconds': seconds
    }


def build_job_list(jobs, apialchemy_info, sqlalchemy_info):
    """Builds list of scheduled jobs to assign to JOBS"""
    job_list = []

    apialchemy_prefix, apialchemy_binds = apialchemy_info
    sqlalchemy_prefix, sqlalchemy_binds = sqlalchemy_info

    service_name_pattern = re.compile(r'^' + r'(?:(?:' + re.escape(apialchemy_prefix) + r')|(?:' + re.escape(sqlalchemy_prefix) + r'))(?P<name>.+)$', re.X)

    for job_name, credentials in jobs.items():
        if 'service' in credentials.keys() and 'interval_minutes' in credentials.keys():
            m = service_name_pattern.match(credentials['service'])

            if m is not None:
                components = m.groupdict()

                service_name = components['name']

                for k, v in credentials.items():
                    if isinstance(v, str):
                        undefined_env_vars, credentials[k] = populate_env_vars(v)

                        if undefined_env_vars:
                            raise ValueError("Job '" + job_name + "' references undefined environment variable(s): " + ", ".join(undefined_env_vars) + ".")

                if service_name in apialchemy_binds.keys():
                    if 'vendor' in apialchemy_binds[service_name].keys():
                        job_args = [
                            apialchemy_binds[service_name]['vendor'],
                            job_name,
                            service_name,
                            int(credentials['interval_minutes']) * 60
                        ]

                        service_job_args = None

                        if apialchemy_binds[service_name]['vendor'] == 'appdynamics':
                            if 'application' in credentials.keys():
                                job_args.append(credentials['application'])

                                if 'metric_path' in credentials.keys():
                                    service_job_args = [
                                        credentials['metric_path'],
                                        credentials['interval_minutes']
                                    ]
                        elif apialchemy_binds[service_name]['vendor'] == 'extrahop':
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
                                static_label_list = filter(None, re.split(r',\s*', credentials['static_labels']))

                                job_args.append([
                                    tuple(filter(None, label_str.split(':'))) for label_str in static_label_list
                                ])

                            job_list.append(build_job(*job_args))

                            continue
                elif service_name in sqlalchemy_binds.keys():
                    if 'statement' in credentials.keys() and 'value_columns' in credentials.keys():
                        job_args = [
                            'database',
                            job_name,
                            service_name,
                            int(credentials['interval_minutes']) * 60,
                            credentials['statement'],
                            credentials['value_columns'].split(',')
                        ]

                        if 'static_labels' in credentials.keys():
                            static_label_list = filter(None, re.split(r',\s*', credentials['static_labels']))

                            job_args.append([
                                tuple(filter(None, label_str.split(':'))) for label_str in static_label_list
                            ])

                        if 'timestamp_column' in credentials.keys():
                            job_args.append(credentials['timestamp_column'])

                            if 'timezone' in sqlalchemy_binds[service_name].keys():
                                timezone = sqlalchemy_binds[service_name]['timezone']
                            else:
                                timezone = os.getenv('DB_DEFAULT_TIMEZONE', 'US/Eastern')

                            job_args.append(timezone)

                        job_list.append(build_job(*job_args))

                        continue
                else:
                    raise ValueError("Service '" + credentials['service'] + "' not found.")

        raise ValueError("Missing required credentials for job '" + job_name + "'.")

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

                                jobs = json.loads(contents, object_pairs_hook=OrderedDict)

                                jobs_source_templates_path = os.getenv('JOBS_SOURCE_TEMPLATES_PATH')

                                if jobs_source_templates_path is not None:
                                    contents = dal.service.get_file_contents(dal.client,
                                                                             jobs_source_org,
                                                                             jobs_source_repo,
                                                                             jobs_source_templates_path,
                                                                             jobs_source_branch)

                                    templates = json.loads(contents, object_pairs_hook=OrderedDict)

                                    jobs = apply_job_templates(jobs, templates)
                        else:
                            raise ValueError("Missing environment variable(s) required for jobs source service '" + jobs_source_service + "'.")
            else:
                raise ValueError("Service '" + jobs_source_service + "' not found.")

    return jobs


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
