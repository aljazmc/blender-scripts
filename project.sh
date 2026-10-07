#!/bin/bash

find scripts -type f -name "*.py" | xargs -I {} sh -c "blender -b -P \"{}\""
