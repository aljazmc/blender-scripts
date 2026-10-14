import bpy
import os
import sys

script_dir = os.path.dirname(__file__)
sys.path.append(script_dir)

from modules.tree import basictree

basictree()

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(script_dir, "tree.blend"))
