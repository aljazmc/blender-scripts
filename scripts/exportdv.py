import bpy
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

render = bpy.context.scene.render
render.filepath = output + ".dv"

render.image_settings.media_type = 'VIDEO'
render.ffmpeg.format = 'DV'
render.ffmpeg.codec = 'DV'

render.resolution_x = 720
render.resolution_y = 576
render.fps = 25
render.fps_base = 1

bpy.ops.render.render(animation=True)
