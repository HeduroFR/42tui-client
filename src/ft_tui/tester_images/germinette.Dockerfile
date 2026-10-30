FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 python3-venv && rm -rf /var/lib/apt/lists/*
ARG TESTER_REPOSITORY
ARG TESTER_REF
RUN git init /source && git -C /source fetch --depth=1 --no-tags "$TESTER_REPOSITORY" "$TESTER_REF" \
    && git -C /source checkout --detach FETCH_HEAD \
    && test "$(git -C /source rev-parse HEAD)" = "$TESTER_REF" \
    && python3 -m venv /opt/germinette-env \
    && /opt/germinette-env/bin/pip install --no-cache-dir \
       'setuptools==75.8.2' 'wheel==0.45.1' 'rich==13.9.4' 'flake8==7.1.2' \
       'mypy==1.15.0' 'python-dotenv==1.1.0' 'pydantic==2.11.3' \
       'numpy==2.2.4' 'pandas==2.2.3' 'matplotlib==3.10.1' 'requests==2.32.3' \
    && /opt/germinette-env/bin/pip install --no-cache-dir --no-deps --no-build-isolation /source \
    && rm -rf /source
ENV HOME=/tmp LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
WORKDIR /project
ENTRYPOINT ["timeout", "--signal=TERM", "--kill-after=5s", "600s", "/opt/germinette-env/bin/python", "-m", "germinette"]
