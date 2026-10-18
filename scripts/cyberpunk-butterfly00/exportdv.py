import bpy
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "build")
os.makedirs(build_dir, exist_ok=True)
sys.path.append(script_dir)

from modules.butterfly00 import butterfly00

butterfly00()

render = bpy.context.scene.render
render.filepath = os.path.join(build_dir, "butterfly00.dv")

render.image_settings.media_type = 'VIDEO'
render.ffmpeg.format = 'DV'
render.ffmpeg.codec = 'DV'

render.resolution_x = 720
render.resolution_y = 576
render.fps = 25
render.fps_base = 1

bpy.ops.render.render(animation=True)
