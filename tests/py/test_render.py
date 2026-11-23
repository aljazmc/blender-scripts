"""Every project renders a picture worth looking at: small test renders of
frames across the animation are neither black nor blown out, have contrast,
change over time, and show the subject, which changes the picture when it is
hidden. Run: python3 -m unittest discover tests/py

Renders at 160x90 with few samples, about a second a frame. Needs Blender on
the PATH; skipped without it.
"""
import unittest

import blender

WIDTH, HEIGHT, SAMPLES = 160, 90, 4
# the renders the checks below sample, across the animation
POINTS = (0.0, 0.25, 0.5, 0.75, 1.0)

# mean luminance (0..1) of a frame: below is black, above is washed out
DARK, BRIGHT = 0.02, 0.85
# share of pixels at or above full white that counts as blown out
CLIPPED_MAX = 0.2
# standard deviation of luminance: below is a flat, featureless picture
CONTRAST_MIN = 0.04
# mean change of luminance between frames: below, the animation doesn't show
CHANGE_MIN = 0.003
# mean change when the subject is hidden: below, the subject doesn't show
SUBJECT_MIN = 0.005

PROBE = f'''
import numpy as np
render = scene.render
render.resolution_x, render.resolution_y = {WIDTH}, {HEIGHT}
render.resolution_percentage = 100
render.image_settings.file_format = "PNG"
render.image_settings.color_mode = "RGB"
if hasattr(scene, "eevee"):
    scene.eevee.taa_render_samples = {SAMPLES}


def shoot(frame, name):
    scene.frame_set(frame)
    render.filepath = os.path.join(TMP, name + ".png")
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(render.filepath)
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    rgb = pixels.reshape(-1, 4)[:, :3]
    # Rec. 709 luminance of the stored, display-referred values
    return rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32), rgb


start, end = scene.frame_start, scene.frame_end
frames = sorted({{round(start + p * (end - start)) for p in {POINTS!r}}})
shots = {{}}
result = {{"frames": []}}
for frame in frames:
    luminance, rgb = shoot(frame, f"frame{{frame}}")
    shots[frame] = luminance
    result["frames"].append({{
        "frame": frame,
        "finite": bool(np.isfinite(rgb).all()),
        "mean": float(luminance.mean()),
        "std": float(luminance.std()),
        "clipped": float((rgb.min(axis=1) >= 0.999).mean()),
    }})
result["changes"] = [float(np.abs(shots[a] - shots[b]).mean())
                     for a, b in zip(frames, frames[1:])]

middle = frames[len(frames) // 2]
hidden = []
for obj in subjects():
    for part in [obj] + list(obj.children_recursive):
        if not part.hide_render:
            part.hide_render = True
            hidden.append(part.name)
if hidden:
    without, _ = shoot(middle, "without")
    result["subject"] = {{"names": [o.name for o in subjects()],
                          "change": float(np.abs(shots[middle] - without).mean())}}
emit(result)
'''


@unittest.skipIf(blender.skip_reason(), blender.skip_reason())
class RenderTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.renders = {project: blender.probe(project, PROBE) for project in blender.projects()}

    def each(self):
        yield from self.renders.items()

    def test_frames_are_exposed(self):
        for project, render in self.each():
            with self.subTest(project=project):
                for frame in render["frames"]:
                    where = f"frame {frame['frame']}"
                    self.assertTrue(frame["finite"], f"{where} has NaN or inf pixels")
                    self.assertGreater(frame["mean"], DARK, f"{where} is black")
                    self.assertLess(frame["mean"], BRIGHT, f"{where} is washed out")
                    self.assertLess(frame["clipped"], CLIPPED_MAX,
                                    f"{where}: {frame['clipped']:.0%} of the pixels are blown out")

    def test_frames_have_contrast(self):
        for project, render in self.each():
            with self.subTest(project=project):
                for frame in render["frames"]:
                    self.assertGreater(frame["std"], CONTRAST_MIN,
                                       f"frame {frame['frame']} is flat (std {frame['std']:.3f})")

    def test_the_animation_shows(self):
        for project, render in self.each():
            with self.subTest(project=project):
                if len(render["frames"]) < 2:
                    continue  # a still
                for (a, b), change in zip(zip(render["frames"], render["frames"][1:]), render["changes"]):
                    self.assertGreater(change, CHANGE_MIN,
                                       f"frames {a['frame']} and {b['frame']} look the same")

    def test_the_subject_shows(self):
        for project, render in self.each():
            with self.subTest(project=project):
                if "subject" not in render:
                    continue  # nothing animated besides the camera
                subject = render["subject"]
                self.assertGreater(subject["change"], SUBJECT_MIN,
                                   f"hiding {', '.join(subject['names'])} hardly changes the picture")


if __name__ == "__main__":
    unittest.main()
