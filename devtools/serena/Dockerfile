FROM php:8.5.11-cli-bookworm

# Serena remains an external GPL-3.0-or-later service. Its exact source and license
# are retained in the image; no Serena implementation is copied into devtools.
ARG SERENA_REVISION=b79e2a55f9d4072084977dd35bd07d31146d88b9
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv git curl ca-certificates libonig-dev \
    && docker-php-ext-install mbstring \
    && rm -rf /var/lib/apt/lists/*
RUN git init /opt/serena-source \
    && git -C /opt/serena-source remote add origin https://github.com/oraios/serena.git \
    && git -C /opt/serena-source fetch --depth=1 origin "$SERENA_REVISION" \
    && git -C /opt/serena-source checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/serena-source rev-parse HEAD)" = "$SERENA_REVISION" \
    && python3 -m venv /opt/serena-env \
    && /opt/serena-env/bin/pip install --no-cache-dir /opt/serena-source
# Match the dependency pinned by this Serena revision, available without runtime network.
RUN curl --fail --location --silent --show-error \
    https://github.com/phpactor/phpactor/releases/download/2025.12.21.1/phpactor.phar \
    --output /opt/phpactor.phar \
    && echo '53bbe9625cd9b5e9b394bc2f595fbad13dbbe6dfc96950c56dea3b5d9a246cc3  /opt/phpactor.phar' | sha256sum --check
COPY entry.py /opt/serena-entry.py
ENV PATH="/opt/serena-env/bin:$PATH" HOME=/tmp/home SERENA_HOME=/tmp/serena PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
ENTRYPOINT ["/opt/serena-env/bin/python", "/opt/serena-entry.py"]
