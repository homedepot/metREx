import os
import re

from prometheus_client.core import CollectorRegistry
from prometheus_client.multiprocess import MultiProcessCollector

collector_registries = {}

prometheus_multiproc_dir = os.getenv('prometheus_multiproc_dir')


def get_pushgateways(aa, apialchemy_info):
    pushgateways = {}

    apialchemy_prefix, apialchemy_binds = apialchemy_info

    service_name_pattern = re.compile(r'^' + r'(?:' + re.escape(apialchemy_prefix) + r')(?P<name>.+)$', re.X)

    api_vendor_pattern = re.compile(r'^(?:(?P<vendor>\w+)(?:\+(?:http|https))?)(?=://)', re.X)

    pushgateway_services = list(filter(None, re.split(r'\s*,\s*', os.getenv('PUSHGATEWAY_SERVICES', ''))))

    for service in pushgateway_services:
        m = service_name_pattern.match(service)

        if m is not None:
            components = m.groupdict()

            service_name = components['name']

            if service_name in apialchemy_binds.keys():
                conn_str = apialchemy_binds[service_name]

                m = api_vendor_pattern.match(conn_str)

                if m is not None:
                    components = m.groupdict()

                    if components['vendor'] == 'pushgateway':
                        from ..api.pushgateway import Pushgateway

                        dal = Pushgateway(aa)
                        dal.init_aa(service_name)

                        pushgateways[service] = dal.client
                    else:
                        raise ValueError("Service '" + service + "' is not a valid Pushgateway.")
            else:
                raise ValueError("Service '" + service + "' not found.")

    return pushgateways


def get_registry(name):
    if name not in collector_registries.keys():
        collector_registries[name] = CollectorRegistry()

        if prometheus_multiproc_dir is not None:
            MultiProcessCollector(collector_registries[name])

    return collector_registries[name]


def register_collector(name, collector):
    job_registry = get_registry(name)

    job_registry.register(collector)


def unregister_collector(name, collector):
    if name in collector_registries.keys():
        collector_registries[name].unregister(collector)

        del collector_registries[name]
