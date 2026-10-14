import math

import bpy
from mathutils import Quaternion, Vector

from modules.nature import Shader, MeshBuilder

# Shared by the creature recipes: rigging, skinning and a few body parts.

# Keyframe every STEP frames; bezier interpolation smooths the frames between.
STEP = 2
SIDES = (("L", 1), ("R", -1))
AXES = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}


def lerp(a, b, factor):
    return a + (b - a) * factor


def smootherstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (x * 6 - 15) + 10)


def add_armature(name, bones):
    # bones: (name, head, tail, parent, radius at head, radius at tail), parents first.
    data = bpy.data.armatures.new(name=name)
    rig = bpy.data.objects.new(name=name, object_data=data)
    bpy.context.collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for bone_name, head, tail, parent, _, _ in bones:
        bone = data.edit_bones.new(bone_name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def segment_distance(p, head, tail):
    # Distance from p to the segment and how far along it the closest point lies.
    axis = tail - head
    t = min(max((p - head).dot(axis) / axis.length_squared, 0.0), 1.0)
    return (p - (head + axis * t)).length, t


def bind(body, rig, bones):
    # Weights each vertex to the bones it sits closest to, measuring the
    # distance in units of each bone's thickness so the slim legs don't grab
    # the belly. Returns each vertex's main bone.
    groups = {name: body.vertex_groups.new(name=name) for name, *_ in bones}
    main = []
    for vertex in body.data.vertices:
        scores = []
        for name, head, tail, _, r0, r1 in bones:
            distance, t = segment_distance(vertex.co, head, tail)
            scores.append((distance / lerp(r0, r1, t), name))
        scores.sort()
        near = [(1 / max(score, 0.05) ** 8, name) for score, name in scores[:3]]
        total = sum(w for w, _ in near)
        for w, name in near:
            if w / total > 0.01:
                groups[name].add([vertex.index], w / total, 'REPLACE')
        main.append(scores[0][1])
    body.parent = rig
    body.modifiers.new(name="Armature", type='ARMATURE').object = rig
    return main


def rigid(obj, rig, bone):
    # A separate part (eye, ear, hoof...) that moves with one bone.
    obj.vertex_groups.new(name=bone).add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
    obj.parent = rig
    obj.modifiers.new(name="Armature", type='ARMATURE').object = rig
    return obj


def surface_point(bvh, guess):
    location, normal, _, _ = bvh.find_nearest(guess)
    return location, normal


def add_sphere(name, location, radius, material, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=location, scale=scale)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj


def add_tube(name, points, radii, material, sides=10):
    # A tapered tube along points, closed at the tip.
    builder = MeshBuilder()
    verts, faces = [], []
    up = Vector((0, 0, 1))
    for k, point in enumerate(points):
        direction = (points[min(k + 1, len(points) - 1)] - points[max(k - 1, 0)]).normalized()
        side = direction.cross(up if abs(direction.z) < 0.95 else Vector((1, 0, 0))).normalized()
        other = direction.cross(side)
        for i in range(sides):
            angle = 2 * math.pi * i / sides
            verts.append(tuple(point + (side * math.cos(angle) + other * math.sin(angle)) * radii[k]))
    for k in range(len(points) - 1):
        for i in range(sides):
            n = (i + 1) % sides
            faces.append([k * sides + i, k * sides + n, (k + 1) * sides + n, (k + 1) * sides + i])
    faces.append(list(range((len(points) - 1) * sides, len(points) * sides)))
    faces.append(list(reversed(range(sides))))
    builder.add(verts, faces)
    return builder.build(name, [material])


def eye_material(iris=(0.25, 0.13, 0.02)):
    # Dark pupil facing out, a coloured iris around it, under a glossy coat.
    shader = Shader("Eye")
    facing = shader.node("ShaderNodeLayerWeight", {"Blend": 0.3}).outputs["Facing"]
    color = shader.ramp(facing, [(0.0, (0.01, 0.008, 0.005)), (0.35, iris), (0.6, tuple(0.25 * c for c in iris))])
    return shader.surface(color, 0.05, Coat_Weight=1.0, Coat_Roughness=0.02)


def turn(rest, turns):
    # Rotations about armature-space axes (X: pitch, Y: roll, Z: yaw for an
    # animal facing -Y), expressed in the bone's rest frame.
    rotation = Quaternion()
    for axis, angle in turns:
        rotation = Quaternion(rest @ AXES[axis], angle) @ rotation
    return rotation


def skin_mesh(name, points, edges, smoothing=0.6):
    # Wraps a graph of (position, radius) nodes in a Skin modifier, smooths it
    # and bakes the result into a plain mesh object.
    mesh = bpy.data.meshes.new(name=f"{name}.Skeleton")
    mesh.from_pydata([tuple(p) for p, _ in points], edges, [])
    obj = bpy.data.objects.new(name=f"{name}.Skeleton", object_data=mesh)
    bpy.context.collection.objects.link(obj)
    skin = obj.modifiers.new(name="Skin", type='SKIN')
    skin.branch_smoothing = smoothing
    for vertex, (_, radius) in zip(mesh.skin_vertices[0].data, points):
        vertex.radius = radius if isinstance(radius, tuple) else (radius, radius)
    mesh.skin_vertices[0].data[0].use_root = True
    subsurf = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.levels = subsurf.render_levels = 2
    depsgraph = bpy.context.evaluated_depsgraph_get()
    body_mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    body_mesh.name = name
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)
    body_mesh.polygons.foreach_set("use_smooth", [True] * len(body_mesh.polygons))
    body = bpy.data.objects.new(name=name, object_data=body_mesh)
    bpy.context.collection.objects.link(body)
    return body


def add_follow_camera(mover, rig, bone, lens, fstop):
    # A camera riding on mover, tracking (and focused on) one of the rig's bones.
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = lens
    camera_data.clip_start = 0.02
    camera_data.clip_end = 1000
    camera_data.dof.use_dof = True
    camera_data.dof.focus_object = rig
    camera_data.dof.focus_subtarget = bone
    camera_data.dof.aperture_fstop = fstop
    camera = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera)
    camera.parent = mover
    track = camera.constraints.new(type='TRACK_TO')
    track.target = rig
    track.subtarget = bone
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    bpy.context.scene.camera = camera
    return camera


def rest_frames(rig):
    # Each pose bone set to quaternions, with its rest orientation for turn().
    rest = {}
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
        rest[bone.name] = bone.bone.matrix_local.to_3x3().inverted()
    return rest


def timeline_frames(step=STEP):
    scene = bpy.context.scene
    frames = list(range(scene.frame_start, scene.frame_end + 1, step))
    if frames[-1] != scene.frame_end:
        frames.append(scene.frame_end)
    return frames
