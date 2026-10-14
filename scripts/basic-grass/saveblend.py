import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.grass import basicgrass

basicgrass()

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(script_dir, "grass.blend"))
