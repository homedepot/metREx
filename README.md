# metREx

SQL query and monitoring system metrics exporter for [Prometheus](https://prometheus.io/). A product of **Reliability Engineering** at [The Home Depot](https://www.homedepot.com/).

Supported database engines include:
- [DB2](https://www.ibm.com/products/db2-database) / [Informix](https://www.ibm.com/products/informix)
- [Microsoft SQL Server](https://www.microsoft.com/en-us/sql-server/default.aspx)
- [MySQL](https://www.mysql.com/)
- [Oracle](https://www.oracle.com/database)
- [PostgreSQL](https://www.postgresql.org/)

Prometheus metrics can be generated from the following monitoring systems:
- [AppDynamics](https://www.appdynamics.com/)
- [ExtraHop](https://www.extrahop.com/)

## Table of Contents

* [Installation](#installation)
  * [Database Engines](#database-engines)
* [Local Environment Setup](#local-environment-setup)
  * [ENV Variables](#env-variables)
* [Configuration: Services](#configuration-services)
  * [Database Connection Parameters](#database-connection-parameters)
  * [API Connection Parameters](#api-connection-parameters)
  * [Encrypting Credentials](#encrypting-credentials)
* [Configuration: Jobs](#configuration-jobs)
  * [Defining Jobs as PCF Services](#defining-jobs-as-pcf-services)
  * [Defining Jobs in a GitHub Repository](#defining-jobs-in-a-github-repository)
  * [Job Parameters](#job-parameters)
  * [About Aggregation](#about-aggregation)
* [Exposing Metrics to a Pushgateway](#exposing-metrics-to-a-pushgateway)
* [Running the Application](#running-the-application)
* [Swagger](#swagger)
* [Testing](#testing)
* [License](#license)

## Installation

```shell
$ pip install metREx
```

### Database Engines

The [SQLAlchemy](https://www.sqlalchemy.org/) package used by this application enables connectivity to a variety of database engines. However, additional packages may need to be installed, depending on which engines are used.

A variation on the above `pip install` command can be used to include specific SQLAlchemy driver packages as needed.*

In the following example, the dialect identifiers `mysql` and `postgres`, supplied in brackets, will install the `pymysql` and `pg8000` driver packages for MySQL and PostgreSQL database connectivity, respectively:

```shell
$ pip install metREx[mysql,postgresql]
```

For convenience, a selection of predefined dialects are available for commonly used SQLAlchemy driver packages:*

| Dialect      | Driver      |
| :---         | :---        |
| `db2`        | `ibm_db2`   |
| `mssql`      | `pymssql`   |
| `mysql`      | `pymysql`   |
| `oracle`     | `cx_oracle` |
| `postgresql` | `pg8000`    |

To install any combination of these SQLAlchemy drivers, substitute their dialect identifiers, delimited by commas, within the brackets shown in the previous example *(see [Supported Drivers](http://docs.sqlalchemy.org/en/latest/core/engines.html#supported-databases) for details about other SQLAlchemy drivers not mapped to the predefined dialects above)*.

*NOTE: Additional client software may also be required for certain database engines. Installation steps will vary depending on the host operating system.

## Local Environment Setup

Create a new `.env` file in the package root, or rename one of the included `.env.example-*` files to `.env`:

```shell
$ cp .env.example-macos-oracle .env
```

### ENV Variables

The following ENV variables can be used to configure various application behaviors:
- **BOILERPLATE_ENV**: (Default: `dev`) The configuration profile applied to running app instances. Possible values: `dev`, `test`, or `prod`.
- **DEBUG**: (Default: `true` if **BOILERPLATE_ENV** is `dev`, or false otherwise) Whether debug mode is enabled.
- **CF_INSTANCE_INTERNAL_IP**: (Default: `127.0.0.1`) The internal IP address of the running app instance. 
- **PORT**: (Default: `5000`) The port on which the application listens for requests.
- **LD_LIBRARY_PATH**: (Linux) A colon-separated list of the directories containing required database client libraries. Required for some SQLAlchemy drivers.
- **DYLD_LIBRARY_PATH**: (macOS) A colon-separated list of the directories containing required database client libraries. Required for some SQLAlchemy drivers.
- **SECRET_KEY**: The secret used to unlock encrypted credentials. May optionally be substituted with the path to a secret key file *(see **SECRET_PATH** below)*.
- **SECRET_PATH**: (Default: `secrets.yml`) The location of the secret key file used to unlock encrypted service credentials. Can be used when the secret is not explicitly defined via an environment variable *(see **SECRET_KEY** above)*.
- **VCAP_APPLICATION**: (Non-PCF environments) A JSON-formatted, non-breaking string containing the application name that appears in the Swagger UI. May optionally be substituted with the path to a JSON file *(see **VCAP_APPLICATION_PATH** below)*.
- **VCAP_APPLICATION_PATH**: (Non-PCF environments; default: `env/vcap_application.json`) The location of a file containing the application name that appears in the Swagger UI. Used as an alternative to collapsing the JSON string into an environment variable value *(see **VCAP_APPLICATION** above)*.
- **VCAP_SERVICES**: (Non-PCF environments) A JSON-formatted, non-breaking string containing the list of user-provided services available to the application at runtime. May optionally be substituted with the path to a JSON file *(see **VCAP_SERVICES_PATH** below)*.
- **VCAP_SERVICES_PATH**: (Non-PCF environments; default: `env/vcap_services.json`) The location of a file containing the list of user-provided services available to the application at runtime. Used as an alternative to collapsing the JSON string into an environment variable value *(see **VCAP_SERVICES** above)*.
- **API_PREFIX**: (Default: `METREX_API_`) The prefix required for all user-provided services containing API connection credentials.
- **DB_PREFIX**: (Default: `METREX_DB_`) The prefix required for all user-provided services containing database connection credentials.
- **JOB_PREFIX**: (Default: `METREX_JOB_`) The prefix required for all user-provided services containing metric exporter job parameters.
- **ERROR_INCLUDE_MESSAGE**: (Default: `true`) Whether to include detailed error messages in API responses. A generic "Internal Server Error" message will be returned on failure when `false`.
- **SUSPEND_JOB_ON_FAILURE**: (Default: `false`) Whether to suspend metric exporter jobs immediately on failure. Suspended jobs may be resumed manually via the Scheduler API or by restarting the application.
- **APIALCHEMY_APPD_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for AppDynamics API connections.
- **APIALCHEMY_EXTRAHOP_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for ExtraHop API connections.
- **APIALCHEMY_GITHUB_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for GitHub API connections.
- **APIALCHEMY_PUSHGATEWAY_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for Pushgateway API connections.
- **DB_DEFAULT_TIMEZONE**: (Default: `US/Eastern`) The default timezone applied to `timestamp_column` values defined in database-sourced metric exporter jobs.
- **JOBS_SOURCE_SERVICE**: The name of the user-provided service containing GitHub API connection credentials.
- **JOBS_SOURCE_ORG**: The name of the GitHub org in which job definitions are hosted.
- **JOBS_SOURCE_REPO**: The name of the GitHub repository in which job definitions are hosted.
- **JOBS_SOURCE_BRANCH**: (Default: `master`) The branch name of the GitHub-hosted job definitions.
- **JOBS_SOURCE_PATH**: The relative file path to GitHub-hosted job definitions.
- **JOBS_SOURCE_REFRESH_INTERVAL**: (Default: `60`) An integer value representing the polling interval, expressed in minutes, for checking a GitHub-hosted job repository for changes to job definitions.
- **PUSHGATEWAY_SERVICE**: The name of the user-provided service containing Pushgateway API connection credentials.
- **MISFIRE_GRACE_TIME**: (Default: `5`) The seconds after the designated runtime that a metric exporter job is still allowed to be run.
- **THREADPOOL_MAX_WORKERS**: (Default: `20`) The maximum number of spawned threads for the default metric exporter job executor.
- **PROCESSPOOL_MAX_WORKERS**: (Default: `10`) The maximum number of spawned processes for the default metric exporter job executor.

## Configuration: Services

This application was designed to run on Pivotal Cloud Foundry (PCF). However, it can also be configured for non-PCF environments.

When running in PCF, the connection parameters used by metric exporter "jobs" are defined via [user-provided service instances](https://docs.cloudfoundry.org/devguide/services/user-provided.html).

In non-PCF environments, services can be defined via a JSON configuration file (default: `env/vcap_services.json`), which mimics the structure of PCF user-provided services, as shown in the following example:

```json
{
  "user-provided": [
    {
      "name": "METREX_DB_EXAMPLE",
      "label": "user-provided",
      "credentials": {
        "name": "database_name",
        "hostname": "mysql.mydomain.com",
        "port": "3306",
        "encrypted": "false",
        "username": "user",
        "password": "password",
        "dialect": "mysql",
        "driver": "pymysql"
      }
    },
    {
      "name": "METREX_API_APPD",
      "label": "user-provided",
      "credentials": {
        "hostname": "appdynamics.mydomain.com",
        "encrypted": "false",
        "username": "user",
        "password": "password",
        "vendor": "appdynamics"
      }
    },
    {
      "name": "METREX_API_EXTRAHOP",
      "label": "user-provided",
      "credentials": {
        "hostname": "extrahop.mydomain.com",
        "encrypted": "false",
        "apikey": "extrahop_apikey",
        "vendor": "extrahop"
      }
    },
    {
      "name": "METREX_API_GITHUB",
      "label": "user-provided",
      "credentials": {
        "hostname": "github.com",
        "encrypted": "false",
        "apikey": "github_apikey",
        "vendor": "github"
      }
    }
  ]
}
```

### Database Connection Parameters

The names assigned to services containing database connection details must begin with the prefix `METREX_DB_` (or the value of the **DB_PREFIX** environment variable). The text that appears after this prefix will be prepended to the names of all Prometheus metrics generated from this service.

For database connections, the following parameters must be included in the `credentials` block:
- `name`: Database or service name
- `hostname`: Server name or IP address
- `port`: Port number
- `encrypted`: "true" (recommended) if `password` value is encrypted or "false" if it is not.
- `username`: User name
- `password`: Password
- `dialect`: Dialect identifier *(refer to table of Dialect/Driver mappings in [Database Engines](#database-engines) section above)*
- `driver`: SQLAlchemy driver *(refer to table of Dialect/Driver mappings in [Database Engines](#database-engines) section above)*
- `timezone`: Database timezone (defaults to value of **DB_DEFAULT_TIMEZONE** env variable)

### API Connection Parameters

The names assigned to services containing API connection details must begin with the prefix `METREX_API_` (or the value of the **API_PREFIX** environment variable). Presently, connectivity to the following APIs is supported:
- [AppDynamics](https://docs.appdynamics.com/display/PRO43/Metric+and+Snapshot+API)
- [ExtraHop](https://docs.extrahop.com/7.9/rest-extract-metrics)
- [GitHub](https://developer.github.com/v3/)*
- [Prometheus Pushgateway](https://github.com/prometheus/pushgateway)**

*GitHub connectivity is provided only as a means to access metric exporter job definitions in a source repository *(see [Defining Jobs in a GitHub Repository](#defining-jobs-in-a-github-repository) section below)*. It cannot be used as a `service` parameter in individual exporter job definitions.

**Pushgateway connectivity is provided to allow exporter job metrics to be forwarded to a Prometheus Pushgateway server *(see [Exposing Metrics to a Pushgateway](#exposing-metrics-to-a-pushgateway) section below)*. It cannot be used as a `service` parameter in individual exporter job definitions.

The parameters to be included in the `credentials` block for each API connection type are shown below.

AppDynamics API connections:
- `hostname`: AppD controller server name or IP address
- `port`: Port number (optional)
- `encrypted`: "true" (recommended) if `password` value is encrypted or "false" if it is not
- `username`: User name
- `password`: Password
- `vendor`: "appdynamics"

ExtraHop API connections:
- `hostname`: ExtraHop server name or IP address
- `port`: Port number (optional)
- `encrypted`: "true" (recommended) if `apikey` value is encrypted or "false" if it is not
- `apikey`: ExtraHop API key
- `vendor`: "extrahop"

GitHub API connections:
- `hostname`: GitHub server name or IP address
- `port`: Port number (optional)
- `encrypted`: "true" (recommended) if `apikey` value is encrypted or "false" if it is not
- `apikey`: GitHub API key
- `vendor`: "github"

Pushgateway API connections:
- `hostname`: Pushgateway server name or IP address (include "https://" for secure server connections)
- `port`: Port number (optional)
- `encrypted`: "true" (recommended) if `password` value is encrypted or "false" if it is not (optional, for connections requiring Basic auth)
- `username`: User name (optional, for connections requiring Basic auth)
- `password`: Password (optional, for connections requiring Basic auth)
- `vendor`: "pushgateway"

### Encrypting Credentials

For security purposes, it is recommended that database passwords and API keys be encrypted, especially when stored in PCF. This application supports the decryption of credentials encrypted via the [cryptofy](https://github.com/homedepot/cryptofy) package.

To configure the application to decrypt a password or API key for a given connection at runtime, set the `encrypted` property to "true" in the `credentials` block, as shown in the following example:

```json
{
  "user-provided": [
    {
      "name": "METREX_DB_EXAMPLE",
      "label": "user-provided",
      "credentials": {
        "name": "database_name",
        "hostname": "mysql.mydomain.com",
        "port": "3306",
        "encrypted": "true",
        "username": "user",
        "password": "Zq4B/mjYV9a4sVBzWiCxz5+tjcXHK2yc4UDVhWJLP2g=",
        "dialect": "mysql",
        "driver": "pymysql"
      }
    },
    {
      "name": "METREX_API_EXTRAHOP",
      "label": "user-provided",
      "credentials": {
        "hostname": "extrahop.mydomain.com",
        "encrypted": "true",
        "apikey": "V37REDWZithWkr9Qu2d/p6uurhpj6kShcYjX0Y6yBWI=",
        "vendor": "extrahop"
      }
    }
  ]
}
```

A "secret" must be supplied to the application in order to unlock encrypted credentials at runtime. This secret must be the same one that was used to encrypt each of the passwords/API keys *(refer to the cryptofy documentation for instructions on generating secrets and encrypting credentials)*.

Secrets may be supplied either by means of the **SECRET_KEY** environment variable or via a YAML-formatted file, the location of which is referenced in the ENV variable **SECRET_PATH**.*

**Method 1**: Environment variable

```dotenv
SECRET_KEY=my_secret
```

**Method 2**: Secrets file (with file path environment variable)

ENV variable:

```dotenv
SECRET_PATH=secrets.yml
```

Contents of `secrets.yml`:

```yaml
secret-key: my_secret
```

*WARNING: Due to their sensitive nature, care should be taken to protect secret keys from being exposed. If defined via an ENV variable, make sure it is not visible to others; else if it is supplied as a secrets file, do NOT store the file in source code!

## Configuration: Jobs

Metric exporter jobs can be defined in either:
- User-provided service instances in PCF, or
- A GitHub repository

### Defining Jobs as Services

If running in PCF, metric exporter jobs can be defined as user-provided services.* All user-provided services containing exporter job definitions must begin with the prefix `METREX_JOB_` (or the value of the **JOB_PREFIX** environment variable).

In non-PCF environments, jobs can be added to the same JSON-formatted configuration file containing the connection services, as shown below:

```json
{
  "user-provided": [
    {
      "name": "METREX_JOB_QUERY_EXAMPLE",
      "label": "user-provided",
      "credentials": {
        "service": "METREX_DB_EXAMPLE",
        "interval_minutes": "5",
        "statement": "SELECT col1, col2, col3 FROM my_table",
        "value_columns": "col1, col2",
        "static_labels": "name:value"
      }
    },
    {
      "name": "METREX_JOB_APPD_EXAMPLE",
      "label": "user-provided",
      "credentials": {
        "service": "METREX_API_APPD",
        "interval_minutes": "15",
        "application": "Application_Name",
        "metric_path": "Business Transaction Performance|Business Transactions|*|*|*"
      }
    },
    {
      "name": "METREX_JOB_EXTRAHOP_EXAMPLE",
      "label": "user-provided",
      "credentials": {
        "service": "METREX_API_EXTRAHOP",
        "interval_minutes": "60",
        "metric_params": {
          "cycle": "auto",
          "object_type": "device",
          "object_ids": [
            9363
          ],
          "metric_category": "http_client",
          "metric_specs": [
            {
              "name": "req"
            }
          ]
        },
        "aggregation": {
          "funcs": [
            "count",
            "sum",
            "95"
          ],
          "threshold": {
            "operator":  ">",
            "value": "10"
          }
        },
        "static_labels": "name:value"
      }
    }
  ]
}
```

*NOTE: Metric exporter jobs defined as user-defined services in PCF may be subject to limitations on size and the total number which may be binded to a single application. For this reason, it may be preferable to define jobs in a source repository instead.

### Defining Jobs in a GitHub Repository

Metric exporter jobs can also be defined via a JSON-formatted config file hosted in GitHub like the one shown below:

```json
{
  "QUERY_EXAMPLE": {
    "service": "METREX_DB_EXAMPLE",
    "interval_minutes": "5",
    "statement": "SELECT col1, col2, col3 FROM my_table",
    "value_columns": "col1, col2",
    "static_labels": "name:value"
  },
  "APPD_EXAMPLE": {
    "service": "METREX_API_APPD",
    "interval_minutes": "15",
    "application": "Application_Name",
    "metric_path": "Business Transaction Performance|Business Transactions|*|*|*"
  },
  "EXTRAHOP_EXAMPLE": {
    "service": "METREX_API_EXTRAHOP",
    "interval_minutes": "60",
    "metric_params": {
      "cycle": "auto",
      "object_type": "device",
      "object_ids": [
        9363
      ],
      "metric_category": "http_client",
      "metric_specs": [
        {
          "name": "req"
        }
      ]
    },
    "aggregation": {
      "funcs": [
        "count",
        "sum",
        "95"
      ],
      "threshold": {
        "operator":  ">",
        "value": "10"
      }
    },
    "static_labels": "name:value"
  }
}
```

There is no prefix requirement for GitHub-hosted job names. However, the name referenced in the job's `service` parameter must match the full service name (prefix included) defined in PCF.

In order for jobs defined in a GitHub repository to be consumed, the following environment variables must be provided:

```dotenv
JOBS_SOURCE_SERVICE=METREX_API_GITHUB
JOBS_SOURCE_ORG=org_name
JOBS_SOURCE_REPO=repo_name
JOBS_SOURCE_PATH=path/to/jobs.json
JOBS_SOURCE_REFRESH_INTERVAL=30
```

Changes to the jobs config file referenced by these env variables will be picked up every *x* minutes, per the value assigned to **JOBS_SOURCE_REFRESH_INTERVAL**, and incorporated into the job scheduler. Unlike changes to user-defined services in PCF, no restart of the application is required for GitHub-hosted job file changes to take effect.

### Job Parameters

The parameters to be included for each metric exporter job type are shown below.

Database queries:
- `service`: The name of the service containing the database connection details
- `interval_minutes`: The interval (in minutes) to wait between each execution of the job
- `statement`: SELECT query
- `value_columns`: A comma-delimited list of one or more column names representing numeric metric values (any columns returned via the query which do not match the names in this list will be used as metric "labels")
- `static_labels`: (optional) A comma-delimited list of `label:value` pairs to apply as static labels for all metrics
- `timestamp_column`: (optional) The name of column containing metric timestamp (ignored when metrics are exposed via Pushgateway)

AppDynamics metrics:
- `service`: The name of the service containing the API connection details
- `interval_minutes`: The interval (in minutes) to wait between each execution of the job
- `application`: The Application name as it appears in AppD (for Database metrics, value is always "Database Monitoring")
- `metric_path`: The AppD metrics path. May include wildcards (`*`).
- `static_labels`: (optional) A comma-delimited list of `label:value` pairs to apply as static labels for all metrics

ExtraHop metrics:
- `service`: The name of the service containing the API connection details
- `interval_minutes`: The interval (in minutes) to wait between each execution of the job
- `metric_params`: The list of parameters passed to the ExtraHop `/metrics` API endpoint
- `metric_name`: The identifier to be used in the Prometheus metric collector name.
- `aggregation`: The list of parameters used to aggregate the values returned from the ExtraHop API *(see [About Aggregation](#about-aggregation) below)*
- `static_labels`: (optional) A comma-delimited list of `label:value` pairs to apply as static labels for all metrics

### About Aggregation

Certain job types *(see "ExtraHop metrics" above)* provide the ability to define aggregation functions to produce metrics from the result data returned by the service.

The `aggregation` parameter group consists of two subgroups: `funcs` and `threshold` *(see example in [Defining Jobs as PCF Services](#defining-jobs-as-pcf-services) above)*

The `funcs` subgroup accepts any combination of the following aggregation functions:
- `avg`
- `count` (default)
- `min`
- `max`
- `sum`

It can also take integer values between 0 and 100, representing the nth percentile.

The optional `threshold` subgroup works much in the same way as a `HAVING` clause in a SQL `GROUP BY`: it filters by values matching defined criteria.*  Here, the criteria are expressed via the `operator` and `value` params.

Supported `operator` values are:
- `>`
- `<`
- `>=`
- `<=`
- `=`
- `<>`
- `!=`

The `value` param must be an integer.

Example: Match all values greater than 10

```json
{
  "JOB_EXAMPLE": {
    "aggregation": {
      "threshold": {
        "operator":  ">",
        "value": "10"
      }
    }
  }
}
```

*NOTE: If no `threshold` is specified, the aggregation function will include all returned values.

## Exposing Metrics to a Pushgateway

Each metric exporter job exposes its own registry endpoint by default at `/metrics/<job_id>`, which can be scraped by a Prometheus process.

Exporter job metrics can optionally be exposed to a [Prometheus Pushgateway](https://github.com/prometheus/pushgateway) service, which may simplify the process of managing jobs in Prometheus. If a Pushgateway service is defined, all new exporter jobs will automatically be exposed to it, and the metrics will in turn be available in Prometheus by means of scraping the Pushgateway.

In order to activate this feature, a Pushgateway service must be registered *(see example below)* and referenced by the **PUSHGATEWAY_SERVICE** env variable.

Pushgateway service definition:

```json
{
  "user-provided": [
    {
      "name": "METREX_API_PUSHGATEWAY",
      "label": "user-provided",
      "credentials": {
        "hostname": "https://pushgateway.mydomain.com",
        "vendor": "pushgateway"
      }
    }
  ]
}
```

ENV variable:

```dotenv
PUSHGATEWAY_SERVICE=METREX_API_PUSHGATEWAY
```

## Running the Application

With the virtual environment activated as shown above, execute the following command:

```shell
$ metrex
```

## Swagger

Open the URL shown in the resulting output from the above command (default: http://127.0.0.1:5000) to access the Swagger UI.

## Testing

Execute the following command from the top-level directory of the cloned repository:

```shell
$ python setup.py test
```

## License

Distributed under the [Apache, version 2.0 license](https://opensource.org/licenses/Apache-2.0).