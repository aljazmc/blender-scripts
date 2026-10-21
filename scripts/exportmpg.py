import bpy
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

render = bpy.context.scene.render
render.filepath = output + ".mpg"

render.image_settings.media_type = 'VIDEO'
render.ffmpeg.format = 'MPEG1'
render.ffmpeg.codec = 'MPEG1'

render.resolution_x = 1920
render.resolution_y = 1080

bpy.ops.render.render(animation=True)
