import bpy
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

scene = bpy.context.scene

scene.frame_set(100)
scene.render.filepath = output + ".bmp"
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'BMP'
scene.render.image_settings.color_mode = 'RGB'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

bpy.ops.render.render(write_still=True)
