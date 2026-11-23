#!/bin/bash
#
# project.sh rejects bad arguments with its usage and a failing exit code,
# before it looks for any program or touches any output.
#
# Run from anywhere: bash tests/sh/test_project.sh

cd "$(dirname "$0")/../.." || exit 1

failures=0

expect_usage() {

    local output code
    output=$(./project.sh "$@" 2>&1)
    code=$?

    if [ "$code" -ne 1 ] || [[ "$output" != *"You should use:"* ]]; then
        echo "FAIL: ./project.sh $* exited with $code, expected 1 and the usage" >&2
        failures=$((failures + 1))
    else
        echo "ok: ./project.sh $*"
    fi

}

expect_usage
expect_usage no-such-project all
expect_usage all no-such-format
expect_usage all png extra arguments

if [ "$failures" -gt 0 ]; then
    echo "FAILED: $failures" >&2
    exit 1
fi
echo "PASS"
