"""Every animated project moves smoothly and keeps its subject in the picture:
keyframes stay inside the frame range, nothing jumps or flips from one frame
to the next, and through every frame the subject (what is animated, apart
from the camera and lights) stays in front of the camera, in the frame and
big enough to see. Run: python3 -m unittest discover tests/py

Needs Blender on the PATH; skipped without it. A still scene, with nothing
animated, passes.
"""
import statistics
import unittest

import blender

# a camera that turns more than this from one frame to the next flips or cuts
CAMERA_TURN_MAX = 15.0  # degrees a frame
# the subject's centre stays at least this far inside the frame's edges
MARGIN = 0.05  # of the frame's width and height
# and the subject is at least this tall or wide in the picture
SIZE_MIN = 0.05  # of the frame's height or width

PROBE = '''
camera = scene.camera
keys = {}
for owner, curves in fcurves().items():
    times = [k.co[0] for c in curves for k in c.keyframe_points]
    if times:
        keys[owner] = [min(times), max(times)]

moving = [o for o in scene.objects if o.animation_data and o.animation_data.action]
paths = {o.name: [] for o in moving}
views = {o.name: [] for o in subjects()}
for frame in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame)
    for obj in moving:
        m = obj.matrix_world
        paths[obj.name].append(list(m.translation) + list(m.to_quaternion()))
    for obj in subjects():
        points = corners(obj)
        if not points:
            points = [obj.matrix_world.translation]
        centre = sum(points, Vector()) / len(points)
        c = world_to_camera_view(scene, camera, centre)
        projected = [world_to_camera_view(scene, camera, p) for p in points]
        views[obj.name].append({
            "frame": frame, "x": c.x, "y": c.y, "depth": c.z,
            "width": max(p.x for p in projected) - min(p.x for p in projected),
            "height": max(p.y for p in projected) - min(p.y for p in projected),
        })
emit({
    "frames": [scene.frame_start, scene.frame_end],
    "camera": camera.name,
    "clip": [camera.data.clip_start, camera.data.clip_end],
    "keys": keys,
    "paths": paths,
    "views": views,
})
'''


def steps(path):
    """(distance, degrees) moved between consecutive frames of a path of
    [x, y, z, qw, qx, qy, qz]."""
    import math
    out = []
    for a, b in zip(path, path[1:]):
        distance = math.dist(a[:3], b[:3])
        dot = abs(sum(p * q for p, q in zip(a[3:], b[3:])))
        degrees = math.degrees(2 * math.acos(min(1.0, dot)))
        out.append((distance, degrees))
    return out


@unittest.skipIf(blender.skip_reason(), blender.skip_reason())
class AnimationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.animations = {project: blender.probe(project, PROBE) for project in blender.projects()}

    def each(self):
        for project, animation in self.animations.items():
            yield project, animation

    def test_keyframes_stay_in_the_frame_range(self):
        for project, animation in self.each():
            with self.subTest(project=project):
                start, end = animation["frames"]
                for owner, (first, last) in animation["keys"].items():
                    self.assertGreaterEqual(first, start, f"{owner} has keys before frame {start}")
                    self.assertLessEqual(last, end, f"{owner} has keys after frame {end}")

    def test_nothing_jumps(self):
        # a step much longer than the usual ones is a teleport: a missing or
        # misplaced keyframe
        for project, animation in self.each():
            with self.subTest(project=project):
                for name, path in animation["paths"].items():
                    distances = sorted(d for d, _ in steps(path))
                    if not distances or distances[-1] < 1e-6:
                        continue
                    usual = statistics.quantiles(distances, n=4)[2] if len(distances) > 3 else distances[-1]
                    self.assertLessEqual(distances[-1], 5 * usual + 0.01,
                                         f"{name} jumps {distances[-1]:.3f} m in one frame, "
                                         f"usually {usual:.3f} m")

    def test_nothing_flips(self):
        for project, animation in self.each():
            with self.subTest(project=project):
                for name, path in animation["paths"].items():
                    turns = sorted(t for _, t in steps(path))
                    if not turns:
                        continue
                    if name == animation["camera"]:
                        self.assertLessEqual(turns[-1], CAMERA_TURN_MAX,
                                             f"the camera turns {turns[-1]:.1f} degrees in one frame")
                    else:
                        # flapping wings turn fast, so compare with the object's own turns
                        usual = statistics.quantiles(turns, n=20)[18] if len(turns) > 19 else turns[-1]
                        self.assertLessEqual(turns[-1], 2 * usual + 2,
                                             f"{name} turns {turns[-1]:.1f} degrees in one frame, "
                                             f"usually up to {usual:.1f}")

    def test_the_subject_stays_in_the_picture(self):
        for project, animation in self.each():
            with self.subTest(project=project):
                near, far = animation["clip"]
                for name, frames in animation["views"].items():
                    for view in frames:
                        where = f"{name} at frame {view['frame']}"
                        self.assertTrue(near < view["depth"] < far,
                                        f"{where} is {view['depth']:.2f} m from the camera, "
                                        f"outside its clipping range {near}..{far}")
                        self.assertTrue(MARGIN <= view["x"] <= 1 - MARGIN
                                        and MARGIN <= view["y"] <= 1 - MARGIN,
                                        f"{where} leaves the picture: its centre is at "
                                        f"({view['x']:.2f}, {view['y']:.2f}) of the frame")
                        self.assertGreaterEqual(max(view["width"], view["height"]), SIZE_MIN,
                                                f"{where} is too small to see")


if __name__ == "__main__":
    unittest.main()
