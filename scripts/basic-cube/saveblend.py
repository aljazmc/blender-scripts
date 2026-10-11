import bpy
import os
import sys

script_dir = os.path.dirname( __file__ )
sys.path.append( script_dir )

from modules.cube import basiccube as basiccube

filepath = os.path.join( script_dir, "cube.blend" )

basiccube()

bpy.ops.wm.save_as_mainfile(filepath=filepath)

