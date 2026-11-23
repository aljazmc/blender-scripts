"""Runs code inside Blender for the tests, which themselves run on plain
Python: a probe builds a project in Blender's factory startup file, measures
the scene and prints the measurements as JSON, and the test checks them.

Inside Blender, a probe has `scene`, the built scene, and these helpers.
Nothing is written into the repository: the project is built into a
temporary folder that is removed afterwards.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
BLENDER = shutil.which("blender")


def projects():
    """The projects: folders of scripts/ holding <name>.py, where <name> is
    the part of the folder name after its last hyphen."""
    return sorted(folder.name for folder in SCRIPTS.iterdir()
                  if folder.is_dir()
                  and (folder / (folder.name.rsplit("-", 1)[-1] + ".py")).is_file())


PRELUDE = '''
import json, math, os, sys, tempfile
sys.path.insert(0, SCRIPTS_DIR)
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from common import load_project

TMP = tempfile.mkdtemp()
load_project(TMP)
scene = bpy.context.scene
# as the exporters see it: matrix_world is stale until the scene updates
bpy.context.view_layer.update()


def subjects():
    """What the animation is about: animated objects that are neither the
    camera nor a light, and whose parent isn't animated too."""
    def animated(obj):
        return obj is not None and obj.animation_data is not None \\
            and obj.animation_data.action is not None
    return [o for o in scene.objects if animated(o) and o.type not in ("CAMERA", "LIGHT")
            and not animated(o.parent)]


def fcurves():
    """{owner name: [F-curves]} of everything animated: objects, shape keys,
    materials, the world... Blender 4.4 and later keep the F-curves of an
    action in a channel bag per slot; older versions in action.fcurves."""
    from bpy_extras import anim_utils
    found = {}
    for collection in (bpy.data.objects, bpy.data.shape_keys, bpy.data.materials,
                       bpy.data.worlds, bpy.data.cameras, bpy.data.lights,
                       bpy.data.node_groups, bpy.data.meshes):
        for owner in collection:
            data = getattr(owner, "animation_data", None)
            if not data or not data.action:
                continue
            action = data.action
            if hasattr(anim_utils, "action_get_channelbag_for_slot"):
                bag = anim_utils.action_get_channelbag_for_slot(action, data.action_slot)
                curves = list(bag.fcurves) if bag else []
            else:
                curves = list(action.fcurves)
            found[f"{type(owner).__name__} {owner.name}"] = curves
    return found


def corners(obj):
    """World corners of the bounding boxes of an object and its descendants."""
    points = []
    for part in [obj] + list(obj.children_recursive):
        if part.type in ("MESH", "CURVE", "SURFACE", "META", "FONT"):
            points += [part.matrix_world @ Vector(c) for c in part.bound_box]
    return points


def emit(result):
    print("RESULT " + json.dumps(result))
'''


def probe(project, code, timeout=900):
    """Build the project in Blender, run the probe code and return what it
    passed to emit()."""
    script = (PRELUDE.replace("SCRIPTS_DIR", repr(str(SCRIPTS))) + "\n" + code
              + "\nimport shutil\nshutil.rmtree(TMP)\n")
    result = subprocess.run(
        [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1",
         "--python-expr", script, "--", project],
        capture_output=True, text=True, timeout=timeout, cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    lines = [line for line in result.stdout.splitlines() if line.startswith("RESULT ")]
    if result.returncode != 0 or not lines:
        raise AssertionError(f"Blender failed on {project} (exit {result.returncode}):\n"
                             + (result.stdout + result.stderr)[-3000:])
    return json.loads(lines[-1][len("RESULT "):])


def skip_reason():
    if not BLENDER:
        return "needs blender on the PATH"
    if not projects():
        return "no projects"
    return None


if __name__ == "__main__":
    sys.exit("a helper for the tests, not a test")
