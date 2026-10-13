import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.liquid import basicliquid

basicliquid(cache_dir=os.path.join(script_dir, "cache"))

scene = bpy.context.scene
scene.frame_set(scene.frame_end // 2)

bpy.ops.export_scene.gltf(
    filepath=os.path.join(script_dir, "liquid.gltf"),
    export_format="GLTF_SEPARATE",
    use_active_collection=True,
    use_renderable=True
)
