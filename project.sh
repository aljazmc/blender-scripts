#!/bin/bash

require() {

    local bin
    if bin=$(command -v "$1"); then
        echo "$1 found at: $bin"
    else
        echo "$1 is required but was not found" >&2
        exit 1
    fi

}

build() {

    require blender
    require ffmpeg

    find scripts -maxdepth 2 -mindepth 2 -type f -name "*.py" -exec blender -b -P {} \;

}

clean() {

    find scripts -type f ! -name "*.py" -delete
    find scripts -mindepth 2 -type d -empty -delete

}

case "$1" in
    build|clean) "$1" ;;
    *) echo "usage: $0 {build|clean}" >&2; exit 1 ;;
esac
