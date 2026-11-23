"""Every project builds a sound scene in Blender: a camera, the EEVEE renderer
at 1920x1080, valid meshes that all have materials, shaders and a world that
reach their outputs, no missing image files, nothing left outside the scene,
and the same scene on every build. Run: python3 -m unittest discover tests/py

Needs Blender on the PATH; skipped without it.
"""
import unittest

import blender

PROBE = '''
import hashlib
camera = scene.camera
result = {
    "camera": camera.type if camera else None,
    "engine": scene.render.engine,
    "fps": scene.render.fps / scene.render.fps_base,
    "frames": [scene.frame_start, scene.frame_end],
    "resolution": [scene.render.resolution_x, scene.render.resolution_y,
                   scene.render.resolution_percentage],
    "meshes": [],
    "materials": {},
    "world": None,
    "missing_files": [],
    "outside_scene": [o.name for o in bpy.data.objects if o.name not in scene.objects],
}


def reaches_output(tree, output_type):
    outputs = [n for n in tree.nodes if n.bl_idname == output_type]
    active = [n for n in outputs if getattr(n, "is_active_output", True)] or outputs
    return any(n.inputs["Surface"].is_linked for n in active)


fingerprint = hashlib.sha256()
for owner, curves in sorted(fcurves().items()):
    for curve in curves:
        keys = [0.0] * (len(curve.keyframe_points) * 2)
        curve.keyframe_points.foreach_get("co", keys)
        fingerprint.update(f"{owner} {curve.data_path} {curve.array_index} {round(sum(keys), 3)}".encode())
for obj in sorted(scene.objects, key=lambda o: o.name):
    fingerprint.update(f"{obj.name} {obj.type} {tuple(round(v, 4) for v in obj.matrix_world.translation)}".encode())
    if obj.type != "MESH":
        continue
    mesh = obj.data
    coordinates = [0.0] * (len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", coordinates)
    fingerprint.update(f"{len(mesh.vertices)} {round(sum(coordinates), 3)}".encode())
    check = mesh.copy()
    fixed = check.validate(verbose=False)
    bpy.data.meshes.remove(check)
    slots = [slot.material for slot in obj.material_slots]
    result["meshes"].append({
        "name": obj.name,
        "faces": len(mesh.polygons),
        "not_finite": sum(1 for v in coordinates if not math.isfinite(v)),
        "invalid": fixed,
        "slots": len(slots),
        "empty_slots": sum(1 for m in slots if m is None),
    })
    for material in slots:
        if material and material.name not in result["materials"]:
            result["materials"][material.name] = bool(
                material.use_nodes and material.node_tree
                and reaches_output(material.node_tree, "ShaderNodeOutputMaterial"))

world = scene.world
if world:
    result["world"] = bool(world.use_nodes and world.node_tree
                           and reaches_output(world.node_tree, "ShaderNodeOutputWorld"))

for image in bpy.data.images:
    if image.source in ("FILE", "SEQUENCE", "MOVIE") and not image.packed_file:
        if not os.path.exists(bpy.path.abspath(image.filepath)):
            result["missing_files"].append(f"{image.name}: {image.filepath}")

result["fingerprint"] = fingerprint.hexdigest()
emit(result)
'''


@unittest.skipIf(blender.skip_reason(), blender.skip_reason())
class SceneTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scenes = {project: blender.probe(project, PROBE) for project in blender.projects()}

    def each(self):
        yield from self.scenes.items()

    def test_renders_through_a_camera_with_eevee(self):
        for project, scene in self.each():
            with self.subTest(project=project):
                self.assertEqual(scene["camera"], "CAMERA", "scene.camera must be a camera")
                self.assertIn("EEVEE", scene["engine"])

    def test_frame_and_timing(self):
        for project, scene in self.each():
            with self.subTest(project=project):
                self.assertEqual(scene["resolution"], [1920, 1080, 100])
                start, end = scene["frames"]
                self.assertGreaterEqual(start, 0)
                self.assertGreaterEqual(end, start)
                self.assertIn(scene["fps"], (24, 25, 30, 50, 60))

    def test_meshes_are_valid(self):
        for project, scene in self.each():
            with self.subTest(project=project):
                self.assertTrue(scene["meshes"], "no meshes")
                for mesh in scene["meshes"]:
                    self.assertGreater(mesh["faces"], 0, f"{mesh['name']} has no faces")
                    self.assertEqual(mesh["not_finite"], 0, f"{mesh['name']} has NaN or inf coordinates")
                    self.assertFalse(mesh["invalid"], f"{mesh['name']} fails mesh.validate()")

    def test_every_mesh_has_materials(self):
        # a mesh without a material renders flat grey, and exports without one
        for project, scene in self.each():
            with self.subTest(project=project):
                for mesh in scene["meshes"]:
                    self.assertGreater(mesh["slots"], 0, f"{mesh['name']} has no material")
                    self.assertEqual(mesh["empty_slots"], 0, f"{mesh['name']} has empty material slots")

    def test_shaders_reach_their_outputs(self):
        # an unconnected Material Output renders black
        for project, scene in self.each():
            with self.subTest(project=project):
                broken = [name for name, ok in scene["materials"].items() if not ok]
                self.assertEqual(broken, [], "materials whose Surface output isn't connected")
                self.assertIsNotNone(scene["world"], "the scene has no world")
                self.assertTrue(scene["world"], "the world's Surface output isn't connected")

    def test_no_missing_files(self):
        # a missing image renders magenta
        for project, scene in self.each():
            with self.subTest(project=project):
                self.assertEqual(scene["missing_files"], [])

    def test_everything_is_in_the_scene(self):
        # objects outside the scene are neither rendered nor exported
        for project, scene in self.each():
            with self.subTest(project=project):
                self.assertEqual(scene["outside_scene"], [])

    def test_builds_the_same_scene_every_time(self):
        for project, scene in self.scenes.items():
            with self.subTest(project=project):
                again = blender.probe(project, PROBE)
                self.assertEqual(again["fingerprint"], scene["fingerprint"],
                                 "a second build gave another scene")


if __name__ == "__main__":
    unittest.main()
