import math

import bpy
from mathutils import Vector

from modules.nature import Shader, clear_scene, set_timeline, overcast
from modules.body import SIDES, smootherstep, rigid, add_tube
from modules.humanoid import SKIN, CLOTH, Anatomy, build_person, add_head, animate, floor_with

TONE = (0.55, 0.36, 0.25)
GI = (0.78, 0.77, 0.74)
BELT = (0.012, 0.012, 0.012)


def outfit(position, normal, bone):
    # A white cotton gi: wrap jacket with its V at the chest, wide sleeves to
    # mid-forearm, trousers to the ankle; bare hands and feet.
    z = position.z
    if bone.startswith("hand") or bone.startswith("foot") or bone == "neck":
        return TONE, SKIN
    if bone.startswith("forearm") and z < 1.0:
        return TONE, SKIN
    if bone.startswith("shin") and z < 0.14:
        return TONE, SKIN
    if bone == "chest" and normal.y < -0.3 and abs(position.x) < (z - 1.22) * 0.55:
        # The open collar of the jacket.
        return TONE, SKIN
    return GI, CLOTH


def stance(lead=-0.4):
    # Fighting stance: side-on, left foot forward, fists up.
    turns = {
        "hips": [("Z", lead)],
        "spine": [("Z", 0.15)],
        "chest": [("Z", 0.1)],
        "neck": [("Z", -0.25)],
    }
    for side, s in SIDES:
        turns[f"thigh.{side}"] = [("X", -0.3 if s > 0 else 0.15), ("Y", -s * 0.12)]
        turns[f"shin.{side}"] = [("X", 0.35)]
        turns[f"foot.{side}"] = [("X", -0.05 if s > 0 else -0.3), ("Z", s * 0.3)]
        turns[f"upper_arm.{side}"] = [("X", -0.9 if s > 0 else -0.5), ("Y", s * 0.2)]
        turns[f"forearm.{side}"] = [("X", -1.8), ("Z", -s * 0.3)]
        turns[f"hand.{side}"] = [("X", 0.2)]
    return turns


def chamber():
    # The right knee comes up high and the hips start to turn over.
    turns = stance(lead=0.5)
    turns["hips"] = [("Z", 0.5), ("Y", 0.25)]
    turns["thigh.L"] = [("X", -0.05), ("Y", -0.25), ("Z", -0.3)]
    turns["shin.L"] = [("X", 0.2)]
    # Out to the side first, then up in front.
    turns["thigh.R"] = [("Y", 0.9), ("X", -0.9)]
    turns["shin.R"] = [("X", 2.2)]
    turns["foot.R"] = [("X", -0.6)]
    turns["upper_arm.R"] = [("X", -0.2), ("Y", 0.4)]
    turns["forearm.R"] = [("X", -1.2)]
    return turns


def kick():
    # Pivoting on the left foot, hips turned right over, the shin snaps out
    # level at head height.
    turns = chamber()
    turns["hips"] = [("Z", 1.3), ("Y", 0.6)]
    turns["spine"] = [("Y", 0.15), ("Z", -0.2)]
    turns["chest"] = [("Z", -0.2)]
    turns["neck"] = [("Y", -0.4), ("Z", -0.5)]
    turns["thigh.L"] = [("X", 0.0), ("Y", -0.55), ("Z", -0.7)]
    turns["shin.L"] = [("X", 0.12)]
    turns["foot.L"] = [("X", 0.1)]
    turns["thigh.R"] = [("Y", 2.2), ("X", -0.25)]
    turns["shin.R"] = [("X", 0.15)]
    turns["foot.R"] = [("X", -0.9)]
    turns["upper_arm.R"] = [("X", 0.5), ("Y", 0.3)]
    turns["forearm.R"] = [("X", -0.8)]
    turns["upper_arm.L"] = [("X", -1.0), ("Y", -0.1)]
    return turns


def breathe(t):
    b = math.sin(2 * math.pi * 0.8 * t)
    return {"chest": [("X", 0.015 * b)], "upper_arm.L": [("X", 0.03 * b)], "upper_arm.R": [("X", 0.03 * b)]}


KEYS = [
    (0.0, stance(), (0, 0, -0.04), "smooth"),
    (1.4, stance(), (0, 0, -0.04), "smooth"),
    (1.85, chamber(), (0, -0.05, -0.03), "smooth"),
    (2.1, kick(), (0, -0.08, -0.06), "snap"),
    (2.35, kick(), (0, -0.08, -0.06), "smooth"),
    (2.65, chamber(), (0, -0.08, -0.03), "smooth"),
    (3.1, stance(), (0, -0.12, -0.04), "smooth"),
    (5.0, stance(), (0, -0.12, -0.04), "smooth"),
]


def wood_floor_material():
    # Polished dojo boards.
    shader = Shader("Boards")
    coords = shader.coords("Object")
    x, y, _ = shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs
    board = shader.math('FLOOR', shader.math('MULTIPLY', x, 6.0))
    seam = shader.math('LESS_THAN', shader.math('FRACT', shader.math('MULTIPLY', x, 6.0)), 0.015)
    shift = shader.math('FRACT', shader.math('MULTIPLY', board, 0.618))
    grain = shader.noise(shader.node("ShaderNodeCombineXYZ", {0: shader.math('MULTIPLY', x, 60.0), 1: shader.math('ADD', shader.math('MULTIPLY', y, 2.0), shader.math('MULTIPLY', shift, 50.0))}).outputs[0],
                         2.0, detail=6.0, distortion=1.5).outputs["Fac"]
    color = shader.ramp(grain, [(0.3, (0.18, 0.09, 0.04)), (0.7, (0.35, 0.2, 0.09))])
    color = shader.mix(shader.math('MULTIPLY', shift, 0.4), color, (0.25, 0.12, 0.05))
    color = shader.mix(seam, color, (0.03, 0.015, 0.008))
    return shader.surface(color, 0.15, shader.bump(shader.math('ADD', grain, seam), 0.1, 0.002), Coat_Weight=0.4)


def tatami_material():
    # Woven rush mats with black cloth borders.
    shader = Shader("Tatami")
    coords = shader.coords("Object")
    x, y, _ = shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs
    weave = shader.math('SINE', shader.math('MULTIPLY', y, 800.0))
    fibres = shader.noise(shader.coords("Object", (200.0, 4.0, 1.0)), 3.0, detail=4.0).outputs["Fac"]
    u = shader.math('FRACT', shader.math('DIVIDE', x, 0.9))
    v = shader.math('FRACT', shader.math('DIVIDE', y, 1.8))
    border = shader.math('MAXIMUM', shader.math('LESS_THAN', shader.math('MINIMUM', u, shader.math('SUBTRACT', 1.0, u)), 0.04),
                         shader.math('LESS_THAN', shader.math('MINIMUM', v, shader.math('SUBTRACT', 1.0, v)), 0.01))
    color = shader.ramp(fibres, [(0.3, (0.3, 0.3, 0.12)), (0.7, (0.45, 0.42, 0.2))])
    color = shader.mix(border, color, (0.02, 0.02, 0.02))
    return shader.surface(color, 0.7, shader.bump(shader.math('ADD', weave, fibres), 0.2, 0.001), Sheen_Weight=0.3)


def shoji_material():
    # Paper screens glowing with daylight, in a dark wooden lattice.
    shader = Shader("Shoji")
    coords = shader.coords("Object")
    # The plane's own x and y: across and up the wall.
    x, y, _ = shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs
    bar_x = shader.math('LESS_THAN', shader.math('FRACT', shader.math('MULTIPLY', x, 24.0)), 0.04)
    bar_y = shader.math('LESS_THAN', shader.math('FRACT', shader.math('MULTIPLY', y, 8.0)), 0.04)
    frame = shader.math('MAXIMUM', bar_x, bar_y)
    paper = shader.noise(shader.coords("Object"), 80.0, detail=5.0).outputs["Fac"]
    glow = shader.math('MULTIPLY', shader.math('SUBTRACT', 1.0, frame), shader.math('ADD', 1.1, shader.math('MULTIPLY', paper, 0.3)))
    color = shader.mix(frame, (0.85, 0.82, 0.74), (0.05, 0.03, 0.02))
    return shader.surface(color, 0.6, Emission_Color=(1.0, 0.95, 0.85), Emission_Strength=glow)


def add_belt(rig, anatomy):
    # A black belt wrapped round the waist, knotted at the front, ends hanging.
    belt = Shader("Belt")
    weave = belt.noise(belt.coords("Object", (1.0, 1.0, 40.0)), 300.0, detail=2.0).outputs["Fac"]
    belt = belt.surface(BELT, 0.6, belt.bump(weave, 0.3, 0.0005), Sheen_Weight=0.3)
    k = anatomy.k
    waist = anatomy.joints["pelvis"] + Vector((0, 0, 0.06)) * k
    ring = [waist + Vector((0.155 * math.sin(a), -0.12 * math.cos(a), 0)) * k for a in [i * 2 * math.pi / 24 for i in range(25)]]
    rigid(add_tube("Belt", ring, [0.02 * k] * 25, belt, sides=6), rig, "hips")
    knot = waist + Vector((0, -0.125, 0)) * k
    for s in (-1, 1):
        end = [knot, knot + Vector((0.03 * s, -0.02, -0.1)) * k, knot + Vector((0.05 * s, -0.015, -0.22)) * k]
        rigid(add_tube(f"BeltEnd.{s}", end, [0.022 * k, 0.02 * k, 0.018 * k], belt, sides=6), rig, "hips")


def add_dojo(centre):
    floor_with(wood_floor_material(), size=20).location = centre
    bpy.ops.mesh.primitive_plane_add(size=1, location=centre + Vector((0, -0.5, 0.002)))
    mats = bpy.context.active_object
    mats.name = "Tatami"
    mats.scale = (5.4, 7.2, 1)
    mats.data.materials.append(tatami_material())
    bpy.ops.mesh.primitive_plane_add(size=1, location=centre + Vector((0, 6.0, 1.6)), rotation=(math.pi / 2, 0, 0))
    wall = bpy.context.active_object
    wall.name = "Shoji"
    wall.scale = (14, 3.2, 1)
    wall.data.materials.append(shoji_material())
    for name, location, energy, size in (("Key", (-2.5, -5.0, 3.5), 500.0, 2.0), ("Fill", (3.0, -3.0, 3.0), 200.0, 3.0)):
        data = bpy.data.lights.new(name=name, type='AREA')
        data.energy, data.size, data.color = energy, size, (1.0, 0.92, 0.82)
        light = bpy.data.objects.new(name=name, object_data=data)
        bpy.context.collection.objects.link(light)
        light.location = centre + Vector(location)
        light.rotation_euler = (centre + Vector((0, -2.0, 1.0)) - light.location).to_track_quat('-Z', 'Y').to_euler()


def camera_path(t, position):
    # From ahead while walking; for the kick, off to the front left so the
    # leg sweeps across the frame.
    side = smootherstep((t + 0.5) / 1.5)
    walking = (position + Vector((-1.6, -3.6, 1.4)), position + Vector((0, 0, 1.05)))
    kicking = (position + Vector((2.0, -2.9, 1.25)), position + Vector((0.2, -0.2, 1.05)))
    return walking[0].lerp(kicking[0], side), walking[1].lerp(kicking[1], side)


def basickarateist():
    clear_scene()
    set_timeline()
    overcast(color=(0.08, 0.07, 0.06), strength=1.0)
    bpy.context.scene.view_settings.look = 'AgX - Medium High Contrast'
    anatomy = Anatomy(height=1.75, build=1.0)
    rig, _ = build_person("Karateist", anatomy, outfit)
    add_head(rig, anatomy, TONE, hair=(0.02, 0.015, 0.01), hair_style="short")
    add_belt(rig, anatomy)
    add_dojo(Vector((0, -2.5, 0)))
    animate(rig, KEYS, walk_speed=0.8, walk_rate=0.78, camera_path=camera_path, lens=35, fstop=4.0, idle=breathe)
