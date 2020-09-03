import json
import pytz
import re

from urllib import parse

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

    if 'driver' in credentials:
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
        if 'path' in credentials:
            base.append(credentials['path'])
    else:
        username_password = []

        if 'username' in credentials:
            username_password.append(parse.quote(credentials['username']))

        if 'password' in credentials:
            username_password.append(parse.quote(credentials['password']))

        if len(username_password):
            base.append(':'.join(username_password))

        if credentials['dialect'] == 'oracle':
            import cx_Oracle

            base.append(cx_Oracle.makedsn(host=credentials['hostname'],
                                          port=str(credentials['port']),
                                          service_name=credentials['name']))
        else:
            base.append(credentials['hostname'] + ':' + str(credentials['port']) + '/' + credentials['name'])

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
