#!/bin/bash
#
# Helpers for the tests of project.sh: a sandbox with a copy of project.sh, a
# few fake projects and stand-ins for blender and ffmpeg, so a test can run
# project.sh without rendering anything or touching build/ and blend/.
#
# Source it from a test: . "$(dirname "$0")/lib.sh"

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
failures=0

# Make a sandbox and cd into it. The stand-in blender writes each call to
# calls.log and exits with $BLENDER_EXIT (default 0).
sandbox() {

    SANDBOX=$(mktemp -d)
    trap 'rm -rf "$SANDBOX"' EXIT
    cp "$ROOT/project.sh" "$SANDBOX/"
    cd "$SANDBOX" || exit 1

    local project
    for project in cyberpunk-butterfly00 nature-fern01 steampunk-gear02; do
        mkdir -p "scripts/$project"
        touch "scripts/$project/${project##*-}.py"
    done

    mkdir bin
    cat > bin/blender <<'EOF'
#!/bin/bash
echo "blender $*" >> calls.log
exit "${BLENDER_EXIT:-0}"
EOF
    printf '#!/bin/bash\nexit 0\n' > bin/ffmpeg
    chmod +x bin/*
    PATH="$SANDBOX/bin:$PATH"
    : > calls.log

}

# the FORMATS array of project.sh, one per line, without running it
formats() {
    sed -n '/^FORMATS=(/,/^)/p' "${1:-project.sh}" | sed '1d;$d' | tr -s ' ' '\n' | sed '/^$/d'
}

pass() {
    echo "ok: $1"
}

fail() {
    echo "FAIL: $1" >&2
    failures=$((failures + 1))
}

# check <description> <command...>: passes if the command succeeds
check() {
    local description=$1
    shift
    if "$@"; then
        pass "$description"
    else
        fail "$description"
    fi
}

finish() {
    if [ "$failures" -gt 0 ]; then
        echo "FAILED: $failures" >&2
        exit 1
    fi
    echo "PASS"
}
