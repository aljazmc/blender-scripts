import bpy
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

bpy.ops.export_scene.fbx(
    filepath=output + ".fbx",
    bake_anim=True
)
