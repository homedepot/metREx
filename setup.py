import os
import re

from setuptools import find_packages, setup

from discover_tests import DiscoverTest


def str_to_bool(x):
    x = str(x)

    return x.lower() in ('true', 't', 'yes', 'y', '1')


with open(
    os.path.join(os.path.dirname(__file__), 'metREx', '__init__.py')
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

INSTALL_REQUIRES = [
    'cfenv',
    'cryptofy',
    'Flask-APIAlchemy',
    'Flask-APScheduler',
    'flask-restx',
    'Flask-Script',
    'Flask-SQLAlchemy',
    'numpy',
    'prometheus-flask-exporter',
    'python-dotenv',
    'PyYAML',
    'SQLAlchemy'
]

EXTRAS_REQUIRE = {
    'bigquery': [
        'pybigquery'
    ],
    'db2': [
        'ibm-db-sa'
    ],
    'mssql': [
        'pymssql'
    ],
    'mysql': [
        'pymysql'
    ],
    'oracle': [
        'cx-Oracle'
    ],
    'postgresql': [
        'pg8000'
    ]
}

TESTS_REQUIRE = [
    'Flask-Testing',
    'pytest',
    'teamcity-messages'
]

install_all_extras = str_to_bool(os.getenv('INSTALL_ALL_EXTRAS', False))

if install_all_extras:
    for packages in EXTRAS_REQUIRE.values():
        for package in packages:
            if package not in INSTALL_REQUIRES:
                INSTALL_REQUIRES.append(package)

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
      packages=find_packages('metREx'),
      package_dir={
          '': 'metREx'
      },
      data_files=[
          ('static', [
              'favicon.ico'
          ])
      ],
      entry_points={
          'console_scripts': [
              'metrex=manage:run'
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
