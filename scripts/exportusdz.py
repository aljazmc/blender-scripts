import os
import sys

import bpy

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

bpy.ops.wm.usd_export(
    filepath=output + ".usdz",
    export_animation=True
)
