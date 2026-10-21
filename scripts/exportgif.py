import bpy
import os
import sys
import subprocess
import tempfile

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common import load_project

output = load_project("build")

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
        output + ".gif"
    ], check=True)
