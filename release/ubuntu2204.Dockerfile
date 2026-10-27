# Exercise the campus constraint in a disposable non-root account.
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl python3 \
    && rm -rf /var/lib/apt/lists/* && useradd -m student
COPY --chown=student:student release /work/release
COPY --chown=student:student distribution /work/distribution
COPY --chown=student:student dist /work/dist
USER student
ENV HOME=/home/student
WORKDIR /work
RUN test "$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')" = 3.10 \
    && curl --proto '=https' --tlsv1.2 -fsSL https://github.com/astral-sh/uv/releases/download/0.13.3/uv-installer.sh -o /tmp/uv.sh \
    && echo '320a286374f5306c4f8c807bd6a7d504dc318841457cf8f2194bee37fe02a2bd  /tmp/uv.sh' | sha256sum -c - \
    && UV_NO_MODIFY_PATH=1 sh /tmp/uv.sh \
    && /home/student/.local/bin/uv python install --no-bin --no-registry 3.12 \
    && "$(/home/student/.local/bin/uv python find --no-project 3.12)" release/smoke_install.py "$(find dist -name '*.whl' -print -quit)" /home/student/.local/bin/uv \
    && test "$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')" = 3.10
