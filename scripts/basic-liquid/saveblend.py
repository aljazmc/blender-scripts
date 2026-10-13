import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.liquid import basicliquid

basicliquid(cache_dir=os.path.join(script_dir, "cache"))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(script_dir, "liquid.blend"))
