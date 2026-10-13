import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.cube import basiccube

basiccube()

render = bpy.context.scene.render
render.filepath = os.path.join(script_dir, "cube.mp4")

render.image_settings.media_type = 'VIDEO'
render.ffmpeg.format = 'MPEG4'
render.ffmpeg.codec = 'H264'

render.resolution_x = 1920
render.resolution_y = 1080
render.fps = 24

bpy.ops.render.render(animation=True)
