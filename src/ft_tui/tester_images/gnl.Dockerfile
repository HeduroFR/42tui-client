FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3 AS source
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
ARG TESTER_REPOSITORY
ARG TESTER_REF
RUN git init /source && git -C /source fetch --depth=1 --no-tags "$TESTER_REPOSITORY" "$TESTER_REF" \
    && git -C /source checkout --detach FETCH_HEAD \
    && test "$(git -C /source rev-parse HEAD)" = "$TESTER_REF" && rm -rf /source/.git
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN apt-get update && apt-get install -y --no-install-recommends build-essential clang valgrind ncurses-bin python3 && rm -rf /var/lib/apt/lists/*
COPY --from=source /source /opt/gnlTester
COPY --chmod=755 gnl.sh /opt/gnl.sh
ENV HOME=/tmp LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=xterm
WORKDIR /project
ENTRYPOINT ["/opt/gnl.sh"]
