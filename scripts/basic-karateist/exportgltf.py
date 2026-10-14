import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.karateist import basickarateist

basickarateist()

bpy.ops.export_scene.gltf(
    filepath=os.path.join(script_dir, "karateist.gltf"),
    export_format="GLTF_SEPARATE",
    use_active_collection=True,
    export_cameras=True,
    export_bake_animation=True,
    export_animation_mode="SCENE",
    export_apply=True
)
