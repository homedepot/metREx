# metREx

SQL query and monitoring system metrics exporter for [Prometheus](https://prometheus.io/). A product of **Reliability Engineering** at [The Home Depot](https://www.homedepot.com/).

Supported database engines include:
- [DB2](https://www.ibm.com/products/db2-database) / [Informix](https://www.ibm.com/products/informix)
- [Google BigQuery](https://cloud.google.com/bigquery)
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
  * [Defining Jobs as Services](#defining-jobs-as-services)
  * [Defining Jobs in a GitHub Repository](#defining-jobs-in-a-github-repository)
  * [Job Parameters](#job-parameters)
  * [About Aggregation](#about-aggregation)
* [Exposing Metrics to a Pushgateway](#exposing-metrics-to-a-pushgateway)
* [Running the Application](#running-the-application)
* [Running in Docker](#running-in-docker)
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

| Dialect      | Driver       |
| :---         | :---         |
| `bigquery`   | `pybigquery` |
| `db2`        | `ibm_db_sa`  |
| `mssql`      | `pymssql`    |
| `mysql`      | `pymysql`    |
| `oracle`     | `cx_oracle`  |
| `postgresql` | `pg8000`     |

To install any combination of these SQLAlchemy drivers, substitute their dialect identifiers, delimited by commas, within the brackets shown in the previous example *(see [Supported Drivers](http://docs.sqlalchemy.org/en/latest/core/engines.html#supported-databases) for details about other SQLAlchemy drivers not mapped to the predefined dialects above)*.

*NOTE: Additional client software may also be required for certain database engines. Installation steps will vary depending on the host operating system.

## Local Environment Setup

A `.env` file can optionally be used to define environment variables available to the application at runtime. This can be useful when running in a local development environment.

The `.env` file should be placed in the installed package root. Any of the `.env.*` files included in the `examples` folder can be renamed to `.env`, as shown below:

```shell
$ cp examples/.env.macos-oracle metREx/.env
```

### ENV Variables

The following ENV variables can be used to configure various application behaviors:
- **BOILERPLATE_ENV**: (Default: `dev`) The configuration profile applied to running app instances. Possible values: `dev`, `test`, or `prod`.
- **DEBUG**: (Default: `true` if **BOILERPLATE_ENV** is `dev`, or false otherwise) Whether debug mode is enabled.
- **IP_ADDRESS**: (Default: `127.0.0.1`) The internal IP address of the running app instance. 
- **PORT**: (Default: `5000`) The port on which the application listens for requests.
- **LD_LIBRARY_PATH**: (Linux) A colon-separated list of the directories containing required database client libraries. Required for some SQLAlchemy drivers.
- **DYLD_LIBRARY_PATH**: (macOS) A colon-separated list of the directories containing required database client libraries. Required for some SQLAlchemy drivers.
- **GOOGLE_APPLICATION_CREDENTIALS**: The full path to the Google service account credentials JSON file to use as the default for BigQuery connections.
- **SECRET_KEY**: The secret used to unlock encrypted credentials. May optionally be substituted with the path to a secret key file *(see **SECRET_PATH** below)*.
- **SECRET_PATH**: (Default: `secrets.yml`) The location of the secret key file used to unlock encrypted service credentials. Can be used when the secret is not explicitly defined via an environment variable *(see **SECRET_KEY** above)*.
- **SERVICES_PATH**: (Non-CF environments; default: `env/services.yml`) The location of a file containing the list of service connections (and optionally, metric exporter job definitions) available to the application at runtime.
- **API_PREFIX**: (Default: `METREX_API_`) The prefix required for services containing API connection details.
- **DB_PREFIX**: (Default: `METREX_DB_`) The prefix required for services containing database connection details.
- **JOB_PREFIX**: (Default: `METREX_JOB_`) The prefix required for services containing metric exporter job details (not applicable to jobs defined in a GitHub repository).
- **ERROR_INCLUDE_MESSAGE**: (Default: `true`) Whether to include detailed error messages in API responses. A generic "Internal Server Error" message will be returned on failure when `false`.
- **SUSPEND_JOB_ON_FAILURE**: (Default: `false`) Whether to suspend metric exporter jobs immediately on failure. Suspended jobs may be resumed manually via the Scheduler API or by restarting the application.
- **APIALCHEMY_APPD_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for AppDynamics API connections.
- **APIALCHEMY_EXTRAHOP_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for ExtraHop API connections.
- **APIALCHEMY_GITHUB_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for GitHub API connections.
- **APIALCHEMY_PUSHGATEWAY_SSL_VERIFY**: (Default: `true`) Whether to perform certificate verification for Pushgateway API connections.
- **DB_DEFAULT_LOCAL_TZ**: (Default: `UTC`) The localized timezone applied by default to "naive" (non-TZ-aware) `timestamp_column` values* if defined in database-sourced metric exporter jobs (consult the [Time Zone Database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for a complete list of supported TZ names).
- **JOBS_SOURCE_SERVICE**: The name of the service containing GitHub API connection details.
- **JOBS_SOURCE_ORG**: The name of the GitHub org in which job definitions are hosted.
- **JOBS_SOURCE_REPO**: The name of the GitHub repository in which job definitions are hosted.
- **JOBS_SOURCE_BRANCH**: (Default: `master`) The branch name of the GitHub-hosted job definitions.
- **JOBS_SOURCE_PATH**: The relative file path to GitHub-hosted job definitions.
- **JOBS_SOURCE_REFRESH_INTERVAL**: (Default: `60`) An integer value representing the polling interval, expressed in minutes, for checking a GitHub-hosted job repository for changes to job definitions.
- **PUSHGATEWAY_SERVICES**: The name(s) of the service(s) containing Pushgateway API connection details (comma-delimited, if more than one).
- **MISFIRE_GRACE_TIME**: (Default: `5`) The seconds after the designated runtime that a metric exporter job is still allowed to be run.
- **THREADPOOL_MAX_WORKERS**: (Default: `20`) The maximum number of spawned threads for the default metric exporter job executor.
- **PROCESSPOOL_MAX_WORKERS**: (Default: `10`) The maximum number of spawned processes for the default metric exporter job executor.

*Does not apply to `timestamp_column` values that contain timezone information; can be overridden on a per-service basis with the `timezone` option.

## Configuration: Services

This application was originally designed to run on [Cloud Foundry (CF)](https://github.com/cloudfoundry). However, it can also be configured for other environments.

When running in Cloud Foundry, the connection parameters used by metric exporter "jobs" are defined via [user-provided service instances](https://docs.cloudfoundry.org/devguide/services/user-provided.html).

In non-CF environments, services can be defined via a YAML configuration file (default: `env/services.yml`), as shown in the following example:

```yaml
---
METREX_DB_MYSQL_EXAMPLE:
  name: database_name
  hostname: mysql.mydomain.com
  port: 3306
  username: user
  password: password
  encrypted: false
  dialect: mysql
  driver: pymysql
METREX_DB_BIGQUERY_EXAMPLE:
  project: gcp-project-name
  location: US
  credentials_path: /path/to/service/account/credentials.json
  dialect: bigquery
  driver: pybigquery
METREX_API_APPD:
  hostname: appdynamics.mydomain.com
  username: user
  password: password
  encrypted: false
  vendor: appdynamics
METREX_API_EXTRAHOP:
  hostname: extrahop.mydomain.com
  apikey: extrahop_apikey
  encrypted: false
  vendor: extrahop
METREX_API_GITHUB:
  hostname: github.com
  apikey: github_apikey
  encrypted: false
  vendor: github
```

### Database Connection Parameters

The names assigned to services containing database connection details must begin with the prefix `METREX_DB_` (or the value of the **DB_PREFIX** environment variable). The text that appears after this prefix will be prepended to the names of all Prometheus metrics generated from this service.

For database connections (except BigQuery), the following parameters must be included:
- `name`: Database or service name
- `hostname`: Server name or IP address
- `port`: Port number
- `username`: User name
- `password`: Password
- `encrypted`: "true" (recommended) if `password` value is encrypted or "false" if it is not.
- `dialect`: Dialect identifier *(refer to table of Dialect/Driver mappings in [Database Engines](#database-engines) section above)*
- `driver`: SQLAlchemy driver *(refer to table of Dialect/Driver mappings in [Database Engines](#database-engines) section above)*
- `timezone`: Localized [database timezone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to apply to "naive" (non-TZ-aware) `timestamp_column` values returned by metric exporter jobs (optional, to override the **DB_DEFAULT_LOCAL_TZ** env variable)

For BigQuery connections, the following parameters are used:
- `project`: Name of the GCP project (defaults to the project specified in the credentials JSON file)
- `location`: Specifies the dataset location (optional)
- `credentials_path`: Full path to the service account credentials JSON file (optional)*
- `credentials_info`: Contents of the service account credentials JSON file (optional)*
- `encrypted`: "true" (recommended) if the `credentials_info` value is encrypted or "false" if it is not (optional, for use only with `credentials_info`)
- `dialect`: "bigquery"
- `driver`: "pybigquery"

*NOTE: Either `credentials_path` or `credentials_info` can be used instead of or to override the **GOOGLE_APPLICATION_CREDENTIALS** ENV variable on a per-service basis. `credentials_path` takes precedence if provided in combination with **GOOGLE_APPLICATION_CREDENTIALS** or `credentials_info`.

### API Connection Parameters

The names assigned to services containing API connection details must begin with the prefix `METREX_API_` (or the value of the **API_PREFIX** environment variable). Presently, connectivity to the following APIs is supported:
- [AppDynamics](https://docs.appdynamics.com/display/PRO43/Metric+and+Snapshot+API)
- [ExtraHop](https://docs.extrahop.com/7.9/rest-extract-metrics)
- [GitHub](https://developer.github.com/v3/)*
- [Prometheus Pushgateway](https://github.com/prometheus/pushgateway)**

*GitHub connectivity is provided only as a means to access metric exporter job definitions in a source repository *(see [Defining Jobs in a GitHub Repository](#defining-jobs-in-a-github-repository) section below)*. It cannot be used as a `service` parameter in individual exporter job definitions.

**Pushgateway connectivity is provided to allow exporter job metrics to be forwarded to a Prometheus Pushgateway server *(see [Exposing Metrics to a Pushgateway](#exposing-metrics-to-a-pushgateway) section below)*. It cannot be used as a `service` parameter in individual exporter job definitions.

The parameters to be included for each API connection type are shown below.

AppDynamics API connections:
- `hostname`: AppD controller server name or IP address
- `port`: Port number (optional)
- `username`: User name
- `password`: Password
- `encrypted`: "true" (recommended) if `password` value is encrypted or "false" if it is not
- `vendor`: "appdynamics"

ExtraHop API connections:
- `hostname`: ExtraHop server name or IP address
- `port`: Port number (optional)
- `apikey`: ExtraHop API key
- `encrypted`: "true" (recommended) if `apikey` value is encrypted or "false" if it is not
- `vendor`: "extrahop"

GitHub API connections:
- `hostname`: GitHub server name or IP address
- `port`: Port number (optional)
- `apikey`: GitHub API key
- `encrypted`: "true" (recommended) if `apikey` value is encrypted or "false" if it is not
- `vendor`: "github"

Pushgateway API connections:
- `hostname`: Pushgateway server name or IP address (include "https://" for secure server connections)
- `port`: Port number (optional)
- `username`: User name (optional, for connections requiring Basic auth)
- `password`: Password (optional, for connections requiring Basic auth)
- `encrypted`: "true" (recommended) if `password` value is encrypted or "false" if it is not (optional, for connections requiring Basic auth)
- `vendor`: "pushgateway"

### Encrypting Credentials

For security purposes, it is recommended that database passwords and API keys be encrypted, especially when stored in CF. This application supports the decryption of credentials encrypted via the [cryptofy](https://github.com/homedepot/cryptofy) package.

To configure the application to decrypt a password or API key for a given connection at runtime, set the `encrypted` property to "true", as shown in the following example:

```yaml
METREX_DB_MYSQL_EXAMPLE:
  name: database_name
  hostname: mysql.mydomain.com
  port: 3306
  username: user
  password: Zq4B/mjYV9a4sVBzWiCxz5+tjcXHK2yc4UDVhWJLP2g=
  encrypted: true
  dialect: mysql
  driver: pymysql
METREX_API_EXTRAHOP:
  hostname: extrahop.mydomain.com
  apikey: V37REDWZithWkr9Qu2d/p6uurhpj6kShcYjX0Y6yBWI=
  encrypted: true
  vendor: extrahop
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

Metric exporter jobs can be defined via:
- [Service definitions](#defining-jobs-as-services) (user-provided services in CF or the services file)
- [GitHub repository](#defining-jobs-in-a-github-repository)

### Defining Jobs as Services

If running in Cloud Foundry, metric exporter jobs can be defined as user-provided services. All user-provided services containing exporter job definitions must begin with the prefix `METREX_JOB_` (or the value of the **JOB_PREFIX** environment variable).

In non-CF environments, jobs can be added to the same YAML-formatted configuration file containing the connection services, as shown below:

```yaml
METREX_JOB_QUERY_EXAMPLE:
  services:
    - METREX_DB_MYSQL_EXAMPLE
  interval_minutes: 5
  statement: SELECT col1, col2, col3 FROM my_table
  value_columns: col1, col2
  static_labels: name:value
METREX_JOB_APPD_EXAMPLE:
  services:
    - METREX_API_APPD
  interval_minutes: 15
  application: Application_Name
  metric_path: Business Transaction Performance|Business Transactions|*|*|*
METREX_JOB_EXTRAHOP_EXAMPLE:
  services:
    - METREX_API_EXTRAHOP
  interval_minutes: 60
  metric_params:
    cycle: auto
    object_type: device
    object_ids:
      - 9363
    metric_category: http_client
    metric_specs:
      - req
  aggregation:
    funcs:
      - count
      - sum
      - 95
    threshold:
      operator: ">"
      value: 10
  static_labels: name:value
```

### Defining Jobs in a GitHub Repository

Metric exporter jobs can also be defined via a YAML-formatted config file hosted in GitHub like the one shown below:

```yaml
---
QUERY_EXAMPLE:
  services:
    - METREX_DB_MYSQL_EXAMPLE
  interval_minutes: 5
  statement: SELECT col1, col2, col3 FROM my_table
  value_columns: col1, col2
  static_labels: name:value
APPD_EXAMPLE:
  services:
    - METREX_API_APPD
  interval_minutes: 15
  application: Application_Name
  metric_path: Business Transaction Performance|Business Transactions|*|*|*
EXTRAHOP_EXAMPLE:
  services:
    - METREX_API_EXTRAHOP
  interval_minutes: 60
  metric_params:
    cycle: auto
    object_type: device
    object_ids:
      - 9363
    metric_category: http_client
    metric_specs:
      - req
  aggregation:
    funcs:
      - count
      - sum
      - 95
    threshold:
      operator: ">"
      value: 10
  static_labels: name:value
```

There is no prefix requirement for GitHub-hosted job names. However, the name referenced in the job's `service` parameter must match the full service name (prefix included) defined in CF.

In order for jobs defined in a GitHub repository to be consumed, the following environment variables must be provided:

```dotenv
JOBS_SOURCE_SERVICE=METREX_API_GITHUB
JOBS_SOURCE_ORG=org_name
JOBS_SOURCE_REPO=repo_name
JOBS_SOURCE_PATH=path/to/jobs.yml
JOBS_SOURCE_REFRESH_INTERVAL=30
```

Changes to the jobs config file referenced by these env variables will be picked up every *x* minutes, per the value assigned to **JOBS_SOURCE_REFRESH_INTERVAL**, and incorporated into the job scheduler. Unlike changes to services, no restart of the application is required for GitHub-hosted job file changes to take effect.

### Job Parameters

The parameters to be included for each metric exporter job type are shown below.

Database queries:
- `services`: A list of one or more service names containing the database connection details, from which job metrics will be exported
- `interval_minutes`: The interval (in minutes) to wait between each execution of the job
- `statement`: SELECT query
- `value_columns`: A comma-delimited list of one or more column names representing numeric metric values (any columns returned via the query which do not match the names in this list will be used as metric "labels")
- `static_labels`: (optional) A comma-delimited list of `label:value` pairs to apply as static labels for all metrics
- `timestamp_column`: (optional) The name of a column returned by the SQL query to use as the metric timestamp (ignored when metrics are exposed via Pushgateway)

AppDynamics metrics:
- `services`: A list of one or more service names containing the API connection details, from which job metrics will be exported*
- `interval_minutes`: The interval (in minutes) to wait between each execution of the job
- `application`: The Application name as it appears in AppD (for Database metrics, value is always "Database Monitoring")
- `metric_path`: The AppD metrics path. May include wildcards (`*`).
- `static_labels`: (optional) A comma-delimited list of `label:value` pairs to apply as static labels for all metrics

ExtraHop metrics:
- `services`: A list of one or more service names containing the API connection details, from which job metrics will be exported*
- `interval_minutes`: The interval (in minutes) to wait between each execution of the job
- `metric_params`: The list of parameters passed to the ExtraHop `/metrics` API endpoint
- `metric_name`: The identifier to be used in the Prometheus metric collector name.
- `aggregation`: The list of parameters used to aggregate the values returned from the ExtraHop API *(see [About Aggregation](#about-aggregation) below)*
- `static_labels`: (optional) A comma-delimited list of `label:value` pairs to apply as static labels for all metrics

*NOTE: All names listed in the `services` parameter for a given API job must reference the same vendor.

### About Aggregation

Certain job types *(see "ExtraHop metrics" above)* provide the ability to define aggregation functions to produce metrics from the result data returned by the API.

The `aggregation` parameter group consists of two subgroups: `funcs` and `threshold` *(see example in [Defining Jobs as Services](#defining-jobs-as-services) above)*

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

```yaml
JOB_EXAMPLE:
  aggregation:
    threshold:
      operator: ">"
      value: 10
```

*NOTE: If no `threshold` is specified, the aggregation function will include all returned values.

## Exposing Metrics to a Pushgateway

Each metric exporter job exposes its own registry endpoint by default at `/metrics/<job_id>`, which can be scraped by a Prometheus process.

Exporter job metrics can optionally be exposed to one or more [Prometheus Pushgateway](https://github.com/prometheus/pushgateway) services, which may simplify the process of managing jobs in Prometheus. If a Pushgateway service is defined, all new exporter jobs will automatically be exposed to it, and the metrics will in turn be available in Prometheus by means of scraping the Pushgateway.

In order to activate this feature, one or more Pushgateway services must be registered *(see example below)* and referenced (comma-delimited, if more than one) by the **PUSHGATEWAY_SERVICES** env variable.

Pushgateway service definition:

```yaml
METREX_API_PUSHGATEWAY:
  hostname: https://pushgateway.mydomain.com
  vendor: pushgateway
```

ENV variable:

```dotenv
PUSHGATEWAY_SERVICES=METREX_API_PUSHGATEWAY
```

## Running the Application

Execute the following command:

```shell
$ python manage.py run
```

Alternately, the application can be started with the shortcut:

```shell
$ metrex
```

## Running in Docker

This application can be run inside a [Docker](https://www.docker.com/) container. A prepackaged image is available on [Docker Hub](https://hub.docker.com/r/homedepottech/metrex).

It was built with support for the following databases:
- [Google BigQuery](https://cloud.google.com/bigquery)
- [MySQL](https://www.mysql.com/)
- [PostgreSQL](https://www.postgresql.org/)

Sample `docker-compose.yml` file:

```yaml
version: "3.7"

services:
  metrex:
    image: homedepottech/metrex:latest
    ports:
      - 5000:5000
    environment:
      SECRET_PATH: /secrets.yml
      SERVICES_PATH: /services.yml
      GOOGLE_APPLICATION_CREDENTIALS: /gcp_credentials.json
    volumes:
      - /path/to/services.yml:/services.yml
      - /path/to/secrets.yml:/secrets.yml
      - /path/to/gcp_credentials.json:/gcp_credentials.json
```

Create and start the Docker container:

```shell
$ docker-compose up -d metrex
```

## Swagger

Open the URL shown in the resulting output following application startup (default: http://127.0.0.1:5000) to access the Swagger UI.

## Testing

Execute the following command from the top-level directory of the cloned repository:

```shell
$ python setup.py test
```

## License

Distributed under the [Apache, version 2.0 license](https://opensource.org/licenses/Apache-2.0).