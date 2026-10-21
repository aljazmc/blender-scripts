import bpy
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

bpy.ops.wm.usd_export(
    filepath=output + ".usdc",
    export_animation=True
)
