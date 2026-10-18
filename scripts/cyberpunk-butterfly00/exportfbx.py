import bpy
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "build")
os.makedirs(build_dir, exist_ok=True)
sys.path.append(script_dir)

from modules.butterfly00 import butterfly00

butterfly00()

bpy.ops.export_scene.fbx(
    filepath=os.path.join(build_dir, "butterfly00.fbx"),
    bake_anim=True
)
