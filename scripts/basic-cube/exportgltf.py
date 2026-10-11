import bpy
import os
import sys

script_dir = os.path.dirname( __file__ )
sys.path.append( script_dir )

from modules.cube import basiccube as basiccube

filepath = os.path.join( script_dir, "cube.gltf" )

basiccube()

bpy.ops.export_scene.gltf(
    filepath=filepath,
    export_format="GLTF_SEPARATE",
    use_active_collection =True
)
