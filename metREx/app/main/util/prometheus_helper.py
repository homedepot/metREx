import os

from prometheus_client.core import CollectorRegistry
from prometheus_client.multiprocess import MultiProcessCollector

collector_registries = {}

prometheus_multiproc_dir = os.getenv('PROMETHEUS_MULTIPROC_DIR')


def get_registry(name):
    if name not in collector_registries.keys():
        collector_registries[name] = CollectorRegistry()

        if prometheus_multiproc_dir is not None:
            path = os.path.join(prometheus_multiproc_dir, name.lower())

            if os.path.isdir(prometheus_multiproc_dir) and not os.path.isdir(path):
                os.mkdir(path)

            MultiProcessCollector(registry=collector_registries[name], path=path)

    return collector_registries[name]


def register_collector(name, collector):
    job_registry = get_registry(name)

    job_registry.register(collector)


def unregister_collector(name, collector):
    if name in collector_registries.keys():
        collector_registries[name].unregister(collector)

        del collector_registries[name]
