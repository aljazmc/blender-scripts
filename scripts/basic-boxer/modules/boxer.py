import math

import bpy
from mathutils import Vector

from modules.nature import Shader, clear_scene, set_timeline, overcast
from modules.body import SIDES, smootherstep, rigid, add_sphere, add_tube
from modules.humanoid import (SKIN, CLOTH, LEATHER, SATIN, Anatomy, build_person, add_head, animate, leather_material,
                              floor_with)

TONE = (0.5, 0.3, 0.2)
SHORTS = (0.45, 0.02, 0.02)
TRIM = (0.75, 0.73, 0.7)
BOOTS = (0.02, 0.02, 0.022)
WRAPS = (0.7, 0.68, 0.64)


def outfit(position, normal, bone):
    # Bare-chested, in red satin trunks with a white waistband, black boots
    # and white hand wraps.
    z = position.z
    if bone in ("hips",) or (bone.startswith("thigh") and z > 0.62):
        return (TRIM, CLOTH) if z > 0.98 else (SHORTS, SATIN)
    if bone.startswith("foot") or (bone.startswith("shin") and z < 0.33):
        return BOOTS, LEATHER
    if bone.startswith("hand"):
        return WRAPS, CLOTH
    return TONE, SKIN


def guard(lead=-0.5):
    # Orthodox stance: turned side-on, left foot forward, knees soft, hands up
    # by the chin, chin tucked.
    turns = {
        "hips": [("Z", lead)],
        "spine": [("X", 0.08), ("Z", 0.12)],
        "chest": [("Z", 0.1)],
        "neck": [("X", 0.12), ("Z", -0.15)],
        "head": [("X", 0.05)],
    }
    for side, s in SIDES:
        turns[f"thigh.{side}"] = [("X", -0.28 if s > 0 else 0.1), ("Y", -s * 0.1)]
        turns[f"shin.{side}"] = [("X", 0.45)]
        turns[f"foot.{side}"] = [("X", -0.2 if s > 0 else -0.45), ("Z", s * 0.3)]
        turns[f"upper_arm.{side}"] = [("X", -0.8 if s > 0 else -0.65), ("Y", s * 0.3)]
        turns[f"forearm.{side}"] = [("X", -2.1), ("Z", -s * 0.45)]
        turns[f"hand.{side}"] = [("X", 0.25)]
    return turns


def cross():
    # The right cross, straight down the middle: hips and shoulders whip
    # round, the right arm shoots out, the back heel turns up.
    turns = guard(lead=0.15)
    turns["spine"] = [("X", 0.15), ("Z", 0.1)]
    turns["chest"] = [("X", 0.0), ("Z", 0.1)]
    turns["neck"] = [("X", 0.05), ("Z", -0.3)]
    turns["upper_arm.R"] = [("X", -1.8), ("Y", 0.08)]
    turns["forearm.R"] = [("X", -0.08)]
    turns["hand.R"] = [("X", 0.0)]
    turns["thigh.R"] = [("X", 0.25), ("Y", 0.1)]
    turns["shin.R"] = [("X", 0.35)]
    turns["foot.R"] = [("X", -0.8), ("Z", -0.3)]
    turns["thigh.L"] = [("X", -0.45), ("Y", -0.1)]
    return turns


def bounce(t):
    # Light on the feet: a little bob and shuffle in the stance.
    b = math.sin(2 * math.pi * 1.7 * t)
    return {"hips": [("X", 0.02 * b)], "shin.L": [("X", 0.06 * b)], "shin.R": [("X", 0.06 * b)],
            "upper_arm.L": [("X", 0.04 * b)], "upper_arm.R": [("X", 0.04 * math.sin(2 * math.pi * 1.7 * t + 1.0))]}


KEYS = [
    (0.0, guard(), (0, 0, -0.06), "smooth"),
    (2.0, guard(), (0, 0, -0.06), "smooth"),
    (2.15, guard(lead=-0.6), (0, 0.02, -0.07), "smooth"),
    (2.32, cross(), (0, -0.14, -0.09), "snap"),
    (2.5, cross(), (0, -0.14, -0.09), "smooth"),
    (2.95, guard(), (0, -0.05, -0.06), "smooth"),
    (5.0, guard(), (0, -0.05, -0.06), "smooth"),
]


def canvas_material():
    # Ring canvas: a coarse weave, scuffed and stained.
    shader = Shader("Canvas")
    coords = shader.coords("Object")
    x, y, _ = shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs
    weave = shader.math('MULTIPLY', shader.math('SINE', shader.math('MULTIPLY', x, 900.0)), shader.math('SINE', shader.math('MULTIPLY', y, 900.0)))
    stains = shader.noise(coords, 1.2, detail=6.0, roughness=0.65).outputs["Fac"]
    color = shader.ramp(stains, [(0.35, (0.18, 0.24, 0.35)), (0.6, (0.25, 0.32, 0.45)), (0.75, (0.3, 0.33, 0.38))])
    scuffs = shader.noise(coords, 20.0, detail=4.0).outputs["Fac"]
    color = shader.mix(shader.math('GREATER_THAN', scuffs, 0.68), color, (0.4, 0.4, 0.42))
    return shader.surface(color, 0.8, shader.bump(shader.math('ADD', weave, shader.math('MULTIPLY', stains, 2.0)), 0.15, 0.002), Sheen_Weight=0.3)


def add_ring(centre, size):
    # Corner posts, three ropes a side and the canvas.
    floor_with(canvas_material(), size=size + 1.0).location = centre
    rope_colors = [(0.5, 0.02, 0.02), (0.75, 0.75, 0.75), (0.02, 0.05, 0.4)]
    ropes = [Shader(f"Rope.{k}").surface(c, 0.4, Coat_Weight=0.4) for k, c in enumerate(rope_colors)]
    post = Shader("Post").surface((0.6, 0.6, 0.62), 0.25, Metallic=1.0)
    pad = leather_material("Pad", (0.35, 0.02, 0.02))
    half = size / 2
    corners = [centre + Vector((sx * half, sy * half, 0)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    for k, corner in enumerate(corners):
        add_tube(f"Post.{k}", [corner, corner + Vector((0, 0, 1.45))], [0.05, 0.05], post, sides=16)
        add_tube(f"Pad.{k}", [corner + Vector((0, 0, 0.3)), corner + Vector((0, 0, 1.35))], [0.11, 0.11], pad, sides=16)
    for k, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1])):
        for level, height in enumerate((0.45, 0.85, 1.25)):
            sag = [a.lerp(b, f) + Vector((0, 0, height - 0.04 * math.sin(math.pi * f))) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
            add_tube(f"Rope.{k}.{level}", sag, [0.025] * 5, ropes[level], sides=10)


def add_lights(centre):
    # Dark arena; a hard key light over the ring and a cool rim from behind.
    for name, location, energy, color, size in (("Key", (1.5, -4.0, 5.0), 700.0, (1.0, 0.93, 0.85), 1.5),
                                                ("Top", (0.0, -2.0, 6.0), 500.0, (1.0, 0.97, 0.92), 3.0),
                                                ("Rim", (-2.0, 1.0, 3.0), 400.0, (0.7, 0.8, 1.0), 1.0)):
        data = bpy.data.lights.new(name=name, type='AREA')
        data.energy, data.color, data.size = energy, color, size
        light = bpy.data.objects.new(name=name, object_data=data)
        bpy.context.collection.objects.link(light)
        light.location = centre + Vector(location)
        light.rotation_euler = (centre + Vector((0, -1.5, 1.2)) - light.location).to_track_quat('-Z', 'Y').to_euler()


def add_gloves(rig, anatomy):
    # Laced red leather gloves over the fists, with white cuffs.
    glove = leather_material("Glove", (0.4, 0.015, 0.015))
    glove.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 0.6
    cuff = Shader("Cuff").surface((0.75, 0.74, 0.72), 0.35)
    k = anatomy.k
    for side, s in SIDES:
        wrist, knuckles = anatomy.joints[f"wrist.{side}"], anatomy.joints[f"knuckles.{side}"]
        middle = wrist.lerp(knuckles, 0.85)
        rigid(add_sphere(f"Glove.{side}", middle + Vector((0, -0.01, -0.01)) * k, 0.06 * k, glove, scale=(0.85, 1.0, 1.1)), rig, f"hand.{side}")
        rigid(add_sphere(f"Thumb.{side}", middle + Vector((-0.04 * s, -0.03, 0.01)) * k, 0.025 * k, glove, scale=(1.0, 1.0, 1.6)), rig, f"hand.{side}")
        rigid(add_tube(f"Cuff.{side}", [wrist + Vector((0, 0, 0.06)) * k, wrist - Vector((0, 0, 0.02)) * k], [0.045 * k, 0.05 * k], cuff, sides=16),
              rig, f"forearm.{side}")


def camera_path(t, position):
    # Walking: watched from ahead and to one side. Then the camera closes in,
    # straight in front, so the punch comes right at it.
    near = smootherstep((t + 0.5) / 1.5)
    walking = (position + Vector((1.4, -3.4, 1.55)), position + Vector((0, 0, 1.15)))
    facing = (position + Vector((0.15, -1.9, 1.5)), position + Vector((0, -0.2, 1.38)))
    return walking[0].lerp(facing[0], near), walking[1].lerp(facing[1], near)


def basicboxer():
    clear_scene()
    set_timeline()
    overcast(color=(0.01, 0.01, 0.012), strength=1.0)
    bpy.context.scene.view_settings.look = 'AgX - Medium High Contrast'
    anatomy = Anatomy(height=1.8, build=1.12)
    rig, _ = build_person("Boxer", anatomy, outfit)
    add_head(rig, anatomy, TONE, hair=(0.015, 0.012, 0.01), hair_style="shaved")
    add_gloves(rig, anatomy)
    centre = Vector((0, -2.5, 0))
    add_ring(centre, 8.0)
    add_lights(centre)
    animate(rig, KEYS, walk_speed=0.8, walk_rate=0.75, camera_path=camera_path, lens=35, fstop=2.8, idle=bounce)
