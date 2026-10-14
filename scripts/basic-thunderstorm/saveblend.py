import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.thunderstorm import basicthunderstorm

basicthunderstorm()

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(script_dir, "thunderstorm.blend"))
