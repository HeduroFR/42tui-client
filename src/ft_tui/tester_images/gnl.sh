#!/bin/sh
set -eu
# The upstream Makefile expects student sources in its parent directory.
tester_dir=$(mktemp -d /project/.42tui-gnl-XXXXXX)
trap 'rm -rf "$tester_dir"' EXIT HUP INT TERM
cp -R /opt/gnlTester/. "$tester_dir/"
cd "$tester_dir"
# The pinned source must never update itself during a run.
timeout --signal=TERM --kill-after=5s 600s python3 report.py --report /project/.42tui-gnl-result.json
