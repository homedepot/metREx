import os
import re

from setuptools import find_packages, setup

from discover_tests import DiscoverTest


def get_requirements_from_file(extra=None):
    requirements = []

    filename = 'requirements.txt'

    if extra is not None:
        filename = extra + '-' + filename

    with open(
        os.path.join(os.path.dirname(__file__), 'pip', filename)
    ) as file:
        lines = file.readlines()

        specifier_pattern = re.compile(r"""^(?!-|(?:\s*$))([^\n]+)""", re.S)

        for line in lines:
            m = specifier_pattern.match(line)

            if m is not None:
                requirements.append(m.group(1))

    return requirements


def str_to_bool(x):
    x = str(x)

    return x.lower() in ('true', 't', 'yes', 'y', '1')


with open(
    os.path.join(os.path.dirname(__file__), 'metREx', 'app', '__init__.py')
) as i_file:
    info = i_file.read()

    TITLE = (
        re.compile(r""".*__title__ = ["']([^\n]*)['"]""", re.S).match(info).group(1)
    )

    VERSION = (
        re.compile(r""".*__version__ = ["']([^\n]*)['"]""", re.S).match(info).group(1)
    )

    DESCRIPTION = (
        re.compile(r""".*__description__ = ["']([^\n]*)['"]""", re.S).match(info).group(1)
    )

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as r_file:
    README = r_file.read()

INSTALL_REQUIRES = list(get_requirements_from_file())

EXTRAS = [
    'bigquery',
    'db2',
    'informix',
    'mssql',
    'mysql',
    'oracle',
    'postgresql',
    'sqlite'
]

EXTRAS_REQUIRE = {extra: list(get_requirements_from_file(extra)) for extra in EXTRAS}

install_all_extras = str_to_bool(os.getenv('INSTALL_ALL_EXTRAS', False))

if install_all_extras:
    for specifiers in EXTRAS_REQUIRE.values():
        for specifier in specifiers:
            if specifier not in INSTALL_REQUIRES:
                INSTALL_REQUIRES.append(specifier)

TESTS_REQUIRE = list(get_requirements_from_file('test'))

setup(name=TITLE,
      version=VERSION,
      description=DESCRIPTION,
      long_description=README,
      long_description_content_type='text/markdown',
      license='Apache 2.0',
      keywords='prometheus exporter prometheus-exporter metrics metrics-exporter query-exporter sql sql-exporter appd appd-exporter appdynamics appdynamics-exporter extrahop extrahop-exporter',
      url='https://github.com/homedepot/metREx',
      author='Mike Phillipson',
      author_email='MICHAEL_PHILLIPSON1@homedepot.com',
      packages=find_packages(include=[
          'metREx',
          'metREx.*'
      ]),
      data_files=[
          ('static', [
              'favicon.ico'
          ])
      ],
      entry_points={
          'console_scripts': [
              'metrex=metREx.manage:run'
          ]
      },
      python_requires='>=3.6',
      install_requires=INSTALL_REQUIRES,
      extras_require=EXTRAS_REQUIRE,
      tests_require=TESTS_REQUIRE,
      cmdclass={
          'test': DiscoverTest
      },
      zip_safe=False)
