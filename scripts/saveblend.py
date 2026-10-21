import bpy
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("blend")

bpy.ops.wm.save_as_mainfile(filepath=output + ".blend")
