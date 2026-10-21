#!/bin/bash

FORMATS=(
    abc avi avif bmp cin dpx dv exr fbx flv gif glb gltf hdr jp2 jpg
    mkv mov mp4 mpg obj ogv ply png png100 rgb stl tga tif usd usda usdc usdz
    vob webm webp
)

status=0

require() {

    local bin
    if bin=$(command -v "$1"); then
        echo "$1 found at: $bin"
    else
        echo "$1 is required but was not found" >&2
        exit 1
    fi

}

projects() {

    find scripts -mindepth 1 -maxdepth 1 -type d ! -name __pycache__ -printf '%f\n' | sort

}

output() {

    case "$2" in
        blend) echo "blend/$1.blend" ;;
        png100) echo "build/${1}100.png" ;;
        *) echo "build/$1.$2" ;;
    esac

}

run() {

    local script file
    [ "$2" = "blend" ] && script="saveblend" || script="export$2"
    file=$(output "$1" "$2")

    if [ -e "$file" ]; then
        echo "Skipping $file (already exists)"
        return
    fi

    blender -b --python-exit-code 1 -P "scripts/$script.py" -- "$1" || {
        echo "FAILED: $script for $1" >&2
        status=1
    }

}

remove() {

    local file files=("$(output "$1" "$2")")
    case "$2" in
        gltf) files+=("build/$1.bin") ;;
        obj) files+=("build/$1.mtl") ;;
    esac

    for file in "${files[@]}"; do
        if [ -e "$file" ]; then
            rm -f "$file"
            echo "Removed $file"
        fi
    done

}

process() {

    local format
    if [ "$2" = "all" ]; then
        for format in "${FORMATS[@]}" blend; do
            "$3" "$1" "$format"
        done
    else
        "$3" "$1" "$2"
    fi

}

clean() {

    rm -rf build blend

}

usage() {

    local IFS="|"
    echo "You should use: $0 clean" >&2
    echo "            or: $0 {all|<project>} {all|blend|${FORMATS[*]}}" >&2
    echo "            or: $0 {all|<project>} clean" >&2
    echo "            or: $0 {all|<project>} {blend|${FORMATS[*]}} clean" >&2
    echo "Projects: $(projects | paste -sd' ')" >&2
    exit 1

}

valid_format() {

    local format
    [ "$1" = "all" ] || [ "$1" = "blend" ] && return 0
    for format in "${FORMATS[@]}"; do
        [ "$1" = "$format" ] && return 0
    done
    return 1

}

[ "$1" = "clean" ] && [ $# -eq 1 ] && { clean; exit; }

if [ $# -eq 2 ] && [ "$2" = "clean" ]; then
    format="all"
    action="remove"
elif [ $# -eq 3 ] && [ "$3" = "clean" ]; then
    format="$2"
    action="remove"
elif [ $# -eq 2 ]; then
    format="$2"
    action="run"
else
    usage
fi

valid_format "$format" || usage

if [ "$1" = "all" ]; then
    mapfile -t targets < <(projects)
elif [ -d "scripts/$1" ]; then
    targets=("$1")
else
    usage
fi

if [ "$action" = "run" ]; then
    require blender
    require ffmpeg
fi

for project in "${targets[@]}"; do
    process "$project" "$format" "$action"
done

exit "$status"
