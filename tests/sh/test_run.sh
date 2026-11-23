#!/bin/bash
#
# project.sh runs Blender the right way for each request: in the background,
# failing when the script fails, with the right exporter and the project
# after "--"; for one project or all of them. It skips outputs that exist,
# reports a failed export with exit code 1, and stops when a program it needs
# is missing.
#
# Runs in a sandbox (see lib.sh) with a stand-in blender, so nothing renders.
# Run from anywhere: bash tests/sh/test_run.sh

# shellcheck source=tests/sh/lib.sh
. "$(dirname "$0")/lib.sh"
sandbox

# expect_calls <description> <expected calls.log> -- <project.sh arguments>
expect_calls() {

    local description=$1 expected=$2
    shift 3
    : > calls.log
    ./project.sh "$@" > output.log 2>&1
    if [ "$(cat calls.log)" = "$expected" ]; then
        pass "$description"
    else
        fail "$description: ./project.sh $* ran"$'\n'"$(cat calls.log)"$'\n'"expected"$'\n'"$expected"
    fi

}

expect_calls "one project, one format, in the background, failing with the script" \
    "blender -b --python-exit-code 1 -P scripts/exportmp4.py -- cyberpunk-butterfly00" \
    -- cyberpunk-butterfly00 mp4

expect_calls "blend runs saveblend.py" \
    "blender -b --python-exit-code 1 -P scripts/saveblend.py -- nature-fern01" \
    -- nature-fern01 blend

expect_calls "all runs every project, sorted" \
    "blender -b --python-exit-code 1 -P scripts/exportglb.py -- cyberpunk-butterfly00
blender -b --python-exit-code 1 -P scripts/exportglb.py -- nature-fern01
blender -b --python-exit-code 1 -P scripts/exportglb.py -- steampunk-gear02" \
    -- all glb

: > calls.log
./project.sh steampunk-gear02 all > /dev/null 2>&1
count=$(formats | wc -l)
check "<project> all runs every format and blend ($((count + 1)) runs)" \
    [ "$(wc -l < calls.log)" -eq $((count + 1)) ]
check "and each of them once" [ "$(sort -u calls.log | wc -l)" -eq $((count + 1)) ]

mkdir -p build
touch build/nature-fern01.webm
expect_calls "an existing output is skipped" "" -- nature-fern01 webm
check "and says so" grep -q "Skipping build/nature-fern01.webm" output.log
rm -rf build

BLENDER_EXIT=1 ./project.sh all png > output.log 2>&1
code=$?
check "a failed export exits with 1" [ "$code" -eq 1 ]
check "and names the project" grep -q "FAILED: exportpng for nature-fern01" output.log
check "and goes on with the other projects" [ "$(grep -c FAILED output.log)" -eq 3 ]

# only the stand-ins and the basic tools project.sh uses on the PATH
mkdir tools
for tool in bash find sort head paste; do
    ln -s "$(command -v "$tool")" "tools/$tool"
done
for missing in blender ffmpeg; do
    mv "bin/$missing" "bin/$missing.away"
    PATH="$SANDBOX/bin:$SANDBOX/tools" ./project.sh cyberpunk-butterfly00 png > output.log 2>&1
    code=$?
    mv "bin/$missing.away" "bin/$missing"
    check "without $missing it exits with 1" [ "$code" -eq 1 ]
    check "and names $missing" grep -q "$missing is required" output.log
done

finish
