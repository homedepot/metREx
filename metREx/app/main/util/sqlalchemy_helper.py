import json
import re

from urllib import parse

import pytz

from cryptofy import encoding, decrypt

from .misc_helper import str_to_bool


def build_bind_dict(binds, key=''):
    """Builds dict of connections to assign to SQLALCHEMY_BINDS"""
    bind_dict = {}

    encrypted_credentials = [
        'credentials_info',
        'password'
    ]

    for name, credentials in binds.items():
        if 'encrypted' in credentials.keys():
            if str_to_bool(credentials['encrypted']):
                if key != '':
                    for i in encrypted_credentials:
                        if i in credentials.keys():
                            credentials[i] = decrypt(bytes(key, encoding=encoding), credentials[i]).decode(encoding)
                else:
                    raise ValueError('No secret key found.')

        bind_dict[name] = build_dsn(credentials)

    return bind_dict


def build_dsn(credentials):
    """Constructs SQLAlchemy DSN string from credentials."""
    dialect_driver = [credentials['dialect']]

    if 'driver' in credentials.keys():
        dialect_driver.append(credentials['driver'])

    base = []

    if credentials['dialect'] == 'bigquery':
        project_dataset = []

        if 'project' in credentials.keys():
            project_dataset.append(credentials['project'])
        else:
            project_dataset.append('')

        if 'dataset' in credentials.keys():
            project_dataset.append(credentials['dataset'])
        else:
            if project_dataset[0] == '':
                project_dataset.append('')

        project_dataset_params = ['/'.join(project_dataset)]

        params = {}

        valid_params = [
            'location',
            'dataset_id',
            'arraysize',
            'credentials_path',
            'credentials_info',
            'default_query_job_config'
        ]

        for name in valid_params:
            if name in credentials.keys():
                if isinstance(credentials[name], dict):
                    params[name] = json.dumps(credentials[name], separators=(',', ':'))
                else:
                    params[name] = credentials[name]

        if len(params):
            project_dataset_params.append(parse.urlencode(params))

        base.append('?'.join(project_dataset_params))
    elif credentials['dialect'] == 'sqlite':
        if 'path' in credentials.keys():
            base.append(credentials['path'])
    else:
        hostname_port = [credentials['hostname']]

        if 'port' in credentials.keys():
            hostname_port.append(str(credentials['port']))

        if 'driver' in credentials.keys() and credentials['dialect'] == 'informix' and credentials['driver'] == 'ifx_jdbc':
            hostname_port_database_params = [':'.join(hostname_port)]

            if 'name' in credentials.keys():
                database_params = [credentials['name']]

                params = {
                    'delimident': 'y'
                }

                if 'server' in credentials.keys():
                    params['INFORMIXSERVER'] = credentials['server']

                if 'username' in credentials.keys():
                    params['user'] = credentials['username']

                if 'password' in credentials.keys():
                    params['password'] = credentials['password']

                database_params.append(';'.join(key + '=' + parse.quote(val) for key, val in params.items()))

                hostname_port_database_params.append(':'.join(database_params))

            base.append('/'.join(hostname_port_database_params))
        else:
            username_password = []

            if 'username' in credentials.keys():
                username_password.append(parse.quote(credentials['username']))

            if 'password' in credentials.keys():
                username_password.append(parse.quote(credentials['password']))

            if len(username_password):
                base.append(':'.join(username_password))

            if credentials['dialect'] == 'oracle':
                import cx_Oracle

                dsn = (cx_Oracle.makedsn(
                    host=credentials['hostname'],
                    port=str(credentials['port']),
                    service_name=credentials['name']
                ))

                base.append(dsn)
            else:
                hostname_port_database = [':'.join(hostname_port)]

                if 'name' in credentials.keys():
                    hostname_port_database.append(credentials['name'])

                hostname_port_database_params = ['/'.join(hostname_port_database)]

                if credentials['dialect'] in ['mysql', 'postgresql']:
                    params = {}

                    valid_params = [
                        'ssl_ca',
                        'ssl_cert',
                        'ssl_key'
                    ]

                    for name in valid_params:
                        if name in credentials.keys():
                            params[name] = credentials[name]

                    if len(params):
                        hostname_port_database_params.append(parse.urlencode(params))

                base.append('?'.join(hostname_port_database_params))

    uri = [
        '+'.join(dialect_driver),
        '@'.join(base)
    ]

    return '://'.join(uri)


def parse_services_for_binds(prefix, services):
    binds = {}

    service_name_pattern = re.compile(r'^' + re.escape(prefix) + r'(?P<name>.+)$', re.X)

    for service in services:
        m = service_name_pattern.match(service.name)

        if m is not None:
            components = m.groupdict()

            name = components['name']

            if 'timezone' in service.credentials.keys():
                if service.credentials['timezone'] not in pytz.all_timezones:
                    ValueError("Invalid timezone '" + service.credentials['timezone'] + "' defined for service '" + service.name + "'.")

            binds[name] = service.credentials

    return binds
