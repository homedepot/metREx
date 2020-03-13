import re

from cryptofy import encoding, decrypt


def build_bind_dict(binds, key=''):
    """Builds dict of connections to assign to SQLALCHEMY_BINDS"""
    bind_dict = {}

    for name, credentials in binds.items():
        if 'encrypted' in credentials.keys():
            if credentials['encrypted'] == "true":
                if key != '':
                    credentials['password'] = decrypt(bytes(key, encoding=encoding), credentials['password']).decode(encoding)
                else:
                    raise ValueError('No secret key found.')

        bind_dict[name] = build_dsn(credentials)

    return bind_dict


def build_dsn(credentials):
    """Constructs SQLAlchemy DSN string from credentials."""
    dsn = credentials['dialect'] + '+' + credentials['driver'] + '://' + credentials['username'] + ':' + credentials['password'] + '@'

    if credentials['dialect'] == 'oracle':
        import cx_Oracle

        dsn += cx_Oracle.makedsn(host=credentials['hostname'],
                                 port=credentials['port'],
                                 service_name=credentials['name'])
    else:
        dsn += credentials['hostname'] + ':' + credentials['port'] + '/' + credentials['name']

    return dsn


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
