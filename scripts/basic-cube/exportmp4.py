import bpy
import os
import sys

script_dir = os.path.dirname( __file__ )
sys.path.append( script_dir )

from modules.cube import basiccube as basiccube

filepath = os.path.join( script_dir, "cube.mp4" )

basiccube()

bpy.context.scene.render.filepath = filepath

bpy.context.scene.render.image_settings.media_type = 'VIDEO'
bpy.context.scene.render.ffmpeg.format = 'MPEG4'
bpy.context.scene.render.ffmpeg.codec = 'H264'

bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.fps = 24

bpy.ops.render.render(animation=True)

