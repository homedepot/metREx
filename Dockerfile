# This Dockerfile builds metREx with support for Google BigQuery, Microsoft SQL Server, MySQL, and PostgreSQL
FROM python:3.7-slim AS build-image

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    default-libmysqlclient-dev \
    gcc \
    jq \
    libcurl4-openssl-dev \
    libpq-dev \
    libssl-dev \
    python3-dev \
    unixodbc-dev && \
    pip install virtualenv

WORKDIR /usr/src
COPY . .
ENV PYMSSQL_BUILD_WITH_BUNDLED_FREETDS=1
RUN virtualenv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install ."[bigquery,mssql,mysql,postgresql]"

FROM python:3.7-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libmariadb-dev-compat \
    libodbc1 \
    libpq5 \
    libxml2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build-image /opt/venv /opt/venv

ENV IP_ADDRESS=0.0.0.0 \
    PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"
EXPOSE 5000
CMD ["metrex"]