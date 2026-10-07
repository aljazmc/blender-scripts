#!/bin/bash

if blender_bin=$(command -v blender); then
    echo "blender found at: $blender_bin"
else
    echo "blender is required but was not found" >&2
    exit 1
fi

if ffmpeg_bin=$(command -v ffmpeg); then
    echo "ffmpeg found at: $ffmpeg_bin"
else
    echo "ffmpeg is required but was not found" >&2
    exit 1
fi

build() {

    find scripts -type f -name "*.py" | xargs -I {} sh -c "blender -b -P \"{}\""

}

clean() {

    find scripts -type f ! -name "*.py" -delete

}

"$1"
