# Keep Debian glibc consistent across hosts; select the architecture from the catalog.
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git gcc libc6-dev pkg-config valac meson ninja-build nasm libglib2.0-dev libbsd-dev \
    && rm -rf /var/lib/apt/lists/*
ARG TESTER_REPOSITORY
ARG TESTER_REF
RUN git init /source && git -C /source fetch --depth=1 --no-tags "$TESTER_REPOSITORY" "$TESTER_REF" \
    && git -C /source checkout --detach FETCH_HEAD \
    && test "$(git -C /source rev-parse HEAD)" = "$TESTER_REF" \
    && meson setup /build /source --prefix=/opt/tester --buildtype=release \
    && meson compile -C /build && meson install -C /build \
    && mkdir -p /opt/tester/share \
    && if test -f /source/LICENSE; then cp /source/LICENSE /opt/tester/share/LICENSE; fi

FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
# Student Makefiles compile C; Vala, Meson, Ninja, NASM and Git stay in the builder.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev make binutils libglib2.0-0 libbsd0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/tester /opt/tester
COPY --chmod=755 supra.sh /opt/tester/supra.sh
ARG TESTER_REPOSITORY
ARG TESTER_REF
LABEL org.opencontainers.image.source=$TESTER_REPOSITORY \
      org.opencontainers.image.revision=$TESTER_REF
# Installed binaries have no .git sibling, so upstream background updates cannot run.
ENV HOME=/tmp LANG=C.UTF-8 LC_ALL=C.UTF-8
WORKDIR /project

ENTRYPOINT ["/opt/tester/supra.sh"]
