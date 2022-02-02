import os
import re

from cryptofy import encoding, decrypt

from urllib import parse

from .misc_helper import str_to_bool


def build_conn_str(credentials):
    """Constructs API connection string from credentials."""
    uri = []

    if 'vendor' in credentials.keys():
        base = []

        if 'apikey' in credentials.keys():
            base.append(parse.quote(credentials['apikey']))
        else:
            if credentials['vendor'] == 'appdynamics':
                username_account = []
    
                if 'username' in credentials.keys():
                    username_account.append(parse.quote(credentials['username']))
    
                    if 'account' in credentials.keys():
                        username_account.append(parse.quote(credentials['account']))
    
                if len(username_account):
                    username_account_password = [
                        '@'.join(username_account)
                    ]
    
                    if 'password' in credentials.keys():
                        username_account_password.append(parse.quote(credentials['password']))
    
                    base.append(':'.join(username_account_password))
            else:
                username_password = []
    
                if 'username' in credentials.keys():
                    username_password.append(parse.quote(credentials['username']))
    
                    if 'password' in credentials.keys():
                        username_password.append(parse.quote(credentials['password']))
    
                if len(username_password):
                    base.append(':'.join(username_password))

        hostname_port = []

        scheme = [credentials['vendor']]

        if 'hostname' in credentials.keys():
            url_components = parse.urlparse(credentials['hostname'])

            if url_components.scheme:
                scheme.append(url_components.scheme)

            if url_components.hostname is not None:
                hostname = url_components.hostname
            else:
                hostname = credentials['hostname']

            hostname_port.append(hostname)

        if 'port' in credentials.keys():
            hostname_port.append(str(credentials['port']))

        hostname_port_path = []

        if len(hostname_port):
            hostname_port_path.append(':'.join(hostname_port))

            if credentials['vendor'] == 'appdynamics':
                if 'application' in credentials.keys():
                    hostname_port_path.append(parse.quote(credentials['application']))
            elif credentials['vendor'] == 'newrelic':
                if 'account_id' in credentials.keys():
                    hostname_port_path.append(str(credentials['account_id']))
            elif credentials['vendor'] in ['graphite', 'wavefront']:
                if 'prefix' in credentials.keys():
                    hostname_port_path.append(parse.quote(credentials['prefix']))

        if len(hostname_port_path):
            base.append('/'.join(hostname_port_path))

        uri.append('+'.join(scheme))

        if len(base):
            uri.append('@'.join(base))

    return '://'.join(uri)


def build_bind_dict(binds, key=''):
    """Builds dict of connections to assign to APIALCHEMY_BINDS"""
    bind_dict = {}

    encrypted_credentials = [
        'apikey',
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

        bind_dict[name] = build_conn_str(credentials)

    return bind_dict


def get_default_push_service_names(push_services):
    default_push_service_names = []

    default_push_services = list(filter(None, re.split(r'\s*,\s*', os.getenv('SEND_ALL_JOBS_TO_SERVICES', ''))))

    for services in push_services.values():
        for service, service_name in services.items():
            if service in default_push_services and service_name not in default_push_service_names:
                default_push_service_names.append(service_name)

    return default_push_service_names


def get_push_services(prefix, services):
    push_services = {}

    service_name_pattern = re.compile(r'^' + re.escape(prefix) + r'(?P<name>.+)$', re.X)

    vendors = {
        'graphite': 'Graphite bridge',
        'pushgateway': 'Pushgateway',
        'wavefront': 'Wavefront'
    }

    for service in services:
        m = service_name_pattern.match(service.name)

        if m is not None:
            components = m.groupdict()

            name = components['name']

            if 'vendor' in service.credentials.keys():
                vendor = service.credentials['vendor']

                if vendor in vendors.keys():
                    if vendor not in push_services.keys():
                        push_services[vendor] = {}

                    push_services[vendor][service.name] = name

    return push_services


def parse_services_for_binds(prefix, services):
    binds = {}

    service_name_pattern = re.compile(r'^' + re.escape(prefix) + r'(?P<name>.+)$', re.X)

    for service in services:
        m = service_name_pattern.match(service.name)

        if m is not None:
            components = m.groupdict()

            name = components['name']

            binds[name] = service.credentials

    return binds
