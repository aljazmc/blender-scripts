import os
import sys

import bpy

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

bpy.ops.wm.ply_export(
    filepath=output + ".ply"
)
