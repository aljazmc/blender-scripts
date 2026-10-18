import bpy
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "build")
os.makedirs(build_dir, exist_ok=True)
sys.path.append(script_dir)

from modules.butterfly00 import butterfly00

butterfly00()

scene = bpy.context.scene

scene.frame_set(100)
scene.render.filepath = os.path.join(build_dir, "butterfly00.rgb")
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'IRIS'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

bpy.ops.render.render(write_still=True)
