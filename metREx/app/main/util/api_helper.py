from cryptofy import encoding, decrypt

import re

from urllib import parse

from .misc_helper import str_to_bool


def build_conn_str(credentials):
    """Constructs API connection string from credentials."""
    base = []

    if 'apikey' in credentials:
        base.append(parse.quote(credentials['apikey']))
    else:
        username_password = []

        if 'username' in credentials:
            username_password.append(parse.quote(credentials['username']))

        if 'password' in credentials:
            username_password.append(parse.quote(credentials['password']))

        if len(username_password):
            base.append(':'.join(username_password))

    hostname_port = []

    scheme = [credentials['vendor']]

    if 'hostname' in credentials:
        url_components = parse.urlparse(credentials['hostname'])

        if url_components.scheme:
            scheme.append(url_components.scheme)

        if url_components.hostname is not None:
            hostname = url_components.hostname
        else:
            hostname = credentials['hostname']

        hostname_port.append(hostname)

    if 'port' in credentials:
        hostname_port.append(str(credentials['port']))

    if len(hostname_port):
        base.append(':'.join(hostname_port))

    uri = ['+'.join(scheme)]

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
