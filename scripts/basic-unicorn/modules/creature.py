import math

import bpy
from mathutils import Quaternion, Vector

FPS = 24
DURATION = 10
# Keyframe every STEP frames; bezier interpolation smooths the frames between.
STEP = 2

SIDES = (("L", 1), ("R", -1))
AXES = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def set_timeline():
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FPS * DURATION


def lerp(a, b, factor):
    return a + (b - a) * factor


def smootherstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (x * 6 - 15) + 10)


def set_world_color(color, strength=1.0):
    background = bpy.context.scene.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (*color, 1.0)
    background.inputs["Strength"].default_value = strength


def add_sun(rotation, energy):
    bpy.ops.object.light_add(type='SUN', rotation=rotation)
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = energy
    return sun


def add_material(name, color, roughness=0.5, metallic=0.0, emission=0.0):
    material = bpy.data.materials.new(name=name)
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission
    return material


def add_ramp_material(name, texture, output, stops, roughness=0.5, metallic=0.0, settings=None):
    # Any node with a scalar output (a texture, layer weight, ...) mapped
    # through a colour ramp into the base colour.
    material = add_material(name, stops[0][1], roughness, metallic)
    tree = material.node_tree
    node = tree.nodes.new(type=texture)
    for key, value in (settings or {}).items():
        if key in node.inputs:
            node.inputs[key].default_value = value
        else:
            setattr(node, key, value)
    ramp = tree.nodes.new(type="ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    elements[0].position, elements[0].color = stops[0][0], (*stops[0][1], 1.0)
    elements[1].position, elements[1].color = stops[-1][0], (*stops[-1][1], 1.0)
    for position, color in stops[1:-1]:
        elements.new(position).color = (*color, 1.0)
    tree.links.new(node.outputs[output], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
    return material


def add_ground(color1, color2, size=600, tile=4):
    bpy.ops.mesh.primitive_plane_add(size=size)
    ground = bpy.context.active_object
    ground.name = "Ground"
    material = bpy.data.materials.new(name="Ground")
    nodes = material.node_tree.nodes
    checker = nodes.new(type="ShaderNodeTexChecker")
    checker.inputs["Color1"].default_value = (*color1, 1.0)
    checker.inputs["Color2"].default_value = (*color2, 1.0)
    checker.inputs["Scale"].default_value = size / tile
    material.node_tree.links.new(checker.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    ground.data.materials.append(material)
    return ground


def setup_stage():
    clear_scene()
    set_timeline()
    # AgX washes out saturated colours; Standard keeps the textures vivid.
    bpy.context.scene.view_settings.view_transform = 'Standard'
    set_world_color((0.3, 0.55, 1.0), strength=0.5)
    add_ground((0.25, 0.6, 0.15), (0.18, 0.45, 0.1))
    # Light the side the camera sees (the creature faces -Y, the camera sits at -X).
    add_sun(rotation=(math.radians(50), 0, math.radians(-40)), energy=3.0)


def add_part(parts, obj, bone, material):
    # Every part moves rigidly with one bone: low-poly, segmented style.
    obj.data.materials.append(material)
    obj.vertex_groups.new(name=bone).add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
    parts.append(obj)
    return obj


def add_segment(parts, bone, start, end, radius1, radius2, material, vertices=6):
    # A tapered prism from start to end; radius2 of 0 makes a cone.
    start, end = Vector(start), Vector(end)
    direction = end - start
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius1,
        radius2=radius2,
        depth=direction.length,
        location=(start + end) / 2,
        rotation=Vector((0, 0, 1)).rotation_difference(direction).to_euler(),
    )
    return add_part(parts, bpy.context.active_object, bone, material)


def add_blob(parts, bone, center, size, material, segments=8, rings=5):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1, location=center, scale=size)
    return add_part(parts, bpy.context.active_object, bone, material)


def add_panel(parts, bone, points, material):
    # A single flat face, for wings, membranes and tail fans.
    mesh = bpy.data.meshes.new(name=bone)
    mesh.from_pydata(points, [], [list(range(len(points)))])
    obj = bpy.data.objects.new(name=bone, object_data=mesh)
    bpy.context.collection.objects.link(obj)
    return add_part(parts, obj, bone, material)


def mirror(points, s):
    return [(x * s, y, z) for x, y, z in points]


def join_parts(parts, name):
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    mesh = bpy.context.active_object
    mesh.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return mesh


def add_armature(name, bones):
    # bones: (name, head, tail, parent) with parents listed before children.
    data = bpy.data.armatures.new(name=name)
    rig = bpy.data.objects.new(name=name, object_data=data)
    bpy.context.collection.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for bone_name, head, tail, parent in bones:
        bone = data.edit_bones.new(bone_name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = data.edit_bones[parent]
            bone.use_connect = (bone.parent.tail - bone.head).length < 1e-4
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def skin(mesh, rig):
    mesh.parent = rig
    mesh.modifiers.new(name="Armature", type='ARMATURE').object = rig


def leg_turns(name, phase, swing, lift):
    # Thigh swings back and forth; the lower leg folds while it swings forward.
    raised = max(0.0, -math.cos(phase))
    return {
        f"thigh.{name}": [("X", swing * math.sin(phase))],
        f"shin.{name}": [("X", lift * raised)],
        f"foot.{name}": [("X", -0.5 * lift * raised)],
    }


def turn(rest, turns):
    # Rotations about armature-space axes (X: pitch, Y: roll, Z: yaw for a
    # creature facing -Y), expressed in the bone's rest frame.
    rotation = Quaternion()
    for axis, angle in turns:
        rotation = Quaternion(rest @ AXES[axis], angle) @ rotation
    return rotation


def add_follow_camera(mover, rig, bone):
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = 35
    camera_data.clip_end = 1000
    camera = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera)
    camera.parent = mover
    track = camera.constraints.new(type='TRACK_TO')
    track.target = rig
    track.subtarget = bone
    track.head_tail = 0.5
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    bpy.context.scene.camera = camera
    return camera


def animate_creature(rig, walk, fly, walk_speed, fly_speed, altitude, camera_distance, camera_height, camera_lift, camera_sweep=(200, 160)):
    # walk(t) and fly(t) return ({bone: [(axis, angle), ...]}, bob height).
    # The first half of the timeline walks, the second half flies; the
    # camera rides along with the creature, rising camera_lift above (or
    # sinking below) its walking height during the climb, and swings around
    # it through camera_sweep (degrees; 180 is its right side, 90 behind it).
    scene = bpy.context.scene
    takeoff = (scene.frame_start + scene.frame_end) // 2
    mover = bpy.data.objects.new(name="Mover", object_data=None)
    bpy.context.collection.objects.link(mover)
    rig.parent = mover
    camera = add_follow_camera(mover, rig, "spine")

    rest = {}
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
        rest[bone.name] = bone.bone.matrix_local.to_3x3().inverted()

    frames = list(range(scene.frame_start, scene.frame_end + 1, STEP))
    if frames[-1] != scene.frame_end:
        frames.append(scene.frame_end)
    distance = 0.0
    previous = scene.frame_start
    for frame in frames:
        t = (frame - scene.frame_start) / FPS
        # Wings start beating half a second before takeoff; the climb takes three seconds.
        flight = smootherstep((frame - takeoff) / FPS + 0.5)
        climb = smootherstep((frame - takeoff) / (3 * FPS))
        distance += lerp(walk_speed, fly_speed, flight) * (frame - previous) / FPS
        previous = frame

        walk_turns, walk_bob = walk(t)
        fly_turns, fly_bob = fly(t)
        for bone in rig.pose.bones:
            bone_rest = rest[bone.name]
            rotation = turn(bone_rest, walk_turns.get(bone.name, ())).slerp(
                turn(bone_rest, fly_turns.get(bone.name, ())), flight
            )
            if bone.name == "spine":
                # Nose up while climbing.
                rotation = turn(bone_rest, [("X", -0.35 * math.sin(math.pi * climb))]) @ rotation
            bone.rotation_quaternion = rotation
            bone.keyframe_insert("rotation_quaternion", frame=frame)

        mover.location = (0, -distance, altitude * climb)
        mover.keyframe_insert("location", frame=frame)
        rig.location = (0, 0, lerp(walk_bob, fly_bob, flight))
        rig.keyframe_insert("location", frame=frame)

        progress = (frame - scene.frame_start) / (scene.frame_end - scene.frame_start)
        angle = math.radians(lerp(*camera_sweep, progress))
        height = camera_height + camera_lift * climb
        camera.location = (camera_distance * math.cos(angle), camera_distance * math.sin(angle), height)
        camera.keyframe_insert("location", frame=frame)
