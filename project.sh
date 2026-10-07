#!/bin/bash

FORMATS=(
    abc avi avif bmp cin dpx dv exr fbx flv gif glb gltf hdr jp2 jpg
    mkv mov mp4 mpg obj ogv ply png png100 rgb stl tga tif usd usda usdc usdz
    vob webm webp
)

require() {

    local bin
    if bin=$(command -v "$1"); then
        echo "$1 found at: $bin"
    else
        echo "$1 is required but was not found" >&2
        exit 1
    fi

}

run() {

    require blender
    require ffmpeg

    find scripts -maxdepth 2 -mindepth 2 -type f -name "$1" -exec blender -b -P {} \;

}

blend() {

    run "saveblend.py"

}

build() {

    run "*.py"

}

clean() {

    rm -rf build

}

export_format() {

    run "export$1.py"

}

usage() {

    local IFS="|"
    echo "You should use: $0 {blend|build|clean|${FORMATS[*]}}" >&2
    exit 1

}

case "$1" in
    blend|build|clean) "$1" ;;
    *)
        for format in "${FORMATS[@]}"; do
            [ "$1" = "$format" ] && { export_format "$1"; exit; }
        done
        usage
        ;;
esac
