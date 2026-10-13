import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.particles import basicparticles, make_particles_real

emitter = basicparticles()
make_particles_real(emitter, frame=bpy.context.scene.frame_end // 2)

bpy.ops.export_scene.gltf(
    filepath=os.path.join(script_dir, "particles.gltf"),
    export_format="GLTF_SEPARATE",
    use_active_collection=True
)
