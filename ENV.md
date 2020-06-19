### Supported ENV Variables

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