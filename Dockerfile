# This dockerfile builds metREx with support for Google BigQuery, MySQL, and PostgreSQL
FROM python:3.8-slim AS build-image

RUN apt-get update && \
    apt-get -y install --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    gcc \
    libcurl4-openssl-dev \
    libpq-dev \
    libssl-dev \
    python3-dev \
    unixodbc-dev

WORKDIR /usr/src
COPY . ./
RUN python3 -m venv /virtualenv
ENV PATH="/virtualenv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .[bigquery,mysql,postgresql]


FROM python:3.8-slim

RUN apt-get update && \
    apt-get -y install --no-install-recommends \
    libmariadb-dev-compat \
    libodbc1 \
    libpq5 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src
COPY --from=build-image /usr/src .
COPY --from=build-image /virtualenv /virtualenv
ENV PATH="/virtualenv/bin:$PATH" \
    IP_ADDRESS=0.0.0.0

EXPOSE 5000/tcp

ENTRYPOINT ["metrex"]