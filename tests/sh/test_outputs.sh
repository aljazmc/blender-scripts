#!/bin/bash
#
# project.sh names its outputs as the README says, and its clean commands
# remove exactly those, with the files some exporters write next to them:
# build/<project>.<format>, build/<project>100.png for png100,
# blend/<project>.blend, and build/<project>.bin and .mtl for gltf and obj.
#
# Runs in a sandbox (see lib.sh), so it never touches the real build/ or blend/.
# Run from anywhere: bash tests/sh/test_outputs.sh

# shellcheck source=tests/sh/lib.sh
. "$(dirname "$0")/lib.sh"
sandbox

# expect_outputs <project> <format> <file...>: clean removes the files and no other
expect_outputs() {

    local project=$1 format=$2 file left=()
    shift 2
    mkdir -p build blend
    touch "$@" build/keep.png blend/keep.blend build/nature-fern01.mp4
    ./project.sh "$project" "$format" clean > /dev/null 2>&1
    for file in "$@"; do
        [ -e "$file" ] && left+=("$file")
    done
    if [ "${#left[@]}" -gt 0 ]; then
        fail "./project.sh $project $format clean should remove ${left[*]}"
    elif [ ! -e build/keep.png ] || [ ! -e blend/keep.blend ] || [ ! -e build/nature-fern01.mp4 ]; then
        fail "./project.sh $project $format clean removed other files"
    else
        pass "$project $format -> $*"
    fi
    rm -rf build blend

}

expect_outputs cyberpunk-butterfly00 mp4 build/cyberpunk-butterfly00.mp4
expect_outputs cyberpunk-butterfly00 png build/cyberpunk-butterfly00.png
expect_outputs cyberpunk-butterfly00 png100 build/cyberpunk-butterfly00100.png
expect_outputs cyberpunk-butterfly00 blend blend/cyberpunk-butterfly00.blend
expect_outputs cyberpunk-butterfly00 gltf build/cyberpunk-butterfly00.gltf build/cyberpunk-butterfly00.bin
expect_outputs cyberpunk-butterfly00 obj build/cyberpunk-butterfly00.obj build/cyberpunk-butterfly00.mtl
expect_outputs steampunk-gear02 usdz build/steampunk-gear02.usdz

# <project> clean removes every output of that project, the extra files too
mkdir -p build blend
while IFS= read -r format; do
    case "$format" in
        png100) touch build/cyberpunk-butterfly00100.png ;;
        *) touch "build/cyberpunk-butterfly00.$format" ;;
    esac
done < <(formats)
touch blend/cyberpunk-butterfly00.blend build/cyberpunk-butterfly00.bin \
    build/cyberpunk-butterfly00.mtl build/nature-fern01.png
./project.sh cyberpunk-butterfly00 clean > /dev/null 2>&1
check "<project> clean removes all its outputs" \
    [ -z "$(find build blend -name 'cyberpunk-butterfly00*')" ]
check "<project> clean keeps other projects' outputs" [ -e build/nature-fern01.png ]

./project.sh clean > /dev/null 2>&1
check "clean removes build/" [ ! -e build ]
check "clean removes blend/" [ ! -e blend ]

finish
