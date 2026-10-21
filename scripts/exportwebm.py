import bpy
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

render = bpy.context.scene.render
render.filepath = output + ".webm"

render.image_settings.media_type = 'VIDEO'
render.ffmpeg.format = 'WEBM'
render.ffmpeg.codec = 'WEBM'

render.resolution_x = 1920
render.resolution_y = 1080

bpy.ops.render.render(animation=True)
