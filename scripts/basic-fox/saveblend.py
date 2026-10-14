import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.fox import basicfox

basicfox()

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(script_dir, "fox.blend"))
