#!/bin/bash

build() {

    find scripts -type f -name "*.py" | xargs -I {} sh -c "blender -b -P \"{}\""

}

clean() {

    find scripts -type f ! -name "*.py" -delete

}

"$1"
