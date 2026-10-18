import bpy
import os
import sys
import subprocess
import tempfile

script_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "build")
os.makedirs(build_dir, exist_ok=True)
sys.path.append(script_dir)

from modules.butterfly00 import butterfly00

butterfly00()

scene = bpy.context.scene
render = scene.render

render.image_settings.media_type = 'IMAGE'
render.image_settings.file_format = 'PNG'
render.image_settings.color_mode = 'RGB'

render.resolution_x = 640
render.resolution_y = 360

with tempfile.TemporaryDirectory() as frames_dir:
    render.filepath = os.path.join(frames_dir, "")
    bpy.ops.render.render(animation=True)

    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(render.fps / render.fps_base),
        "-start_number", str(scene.frame_start),
        "-i", os.path.join(frames_dir, "%04d.png"),
        "-vf", "split[a][b];[a]palettegen[p];[b][p]paletteuse",
        "-loop", "0",
        os.path.join(build_dir, "butterfly00.gif")
    ], check=True)
