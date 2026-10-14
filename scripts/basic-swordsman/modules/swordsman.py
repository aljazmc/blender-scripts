import math

from mathutils import Vector

from modules.nature import setup_stage, add_meadow
from modules.body import smootherstep, rigid, add_tube
from modules.humanoid import (SKIN, CLOTH, LEATHER, Anatomy, build_person, add_head, animate, metal_material,
                              leather_material)

TONE = (0.55, 0.37, 0.27)
SHIRT = (0.55, 0.5, 0.4)
JERKIN = (0.16, 0.08, 0.035)
TROUSERS = (0.035, 0.028, 0.022)
BOOTS = (0.08, 0.045, 0.02)
BRACERS = (0.12, 0.06, 0.025)


def outfit(position, normal, bone):
    # A linen shirt under a laced leather jerkin, dark wool trousers, tall
    # boots and leather bracers.
    z = position.z
    if bone.startswith("hand") or bone == "neck":
        return TONE, SKIN
    if bone.startswith("foot") or (bone.startswith("shin") and z < 0.45):
        return BOOTS, LEATHER
    if bone.startswith("forearm"):
        return (BRACERS, LEATHER) if z < 1.08 else (SHIRT, CLOTH)
    if bone.startswith(("upper_arm", "shoulder")):
        return SHIRT, CLOTH
    if bone in ("spine", "chest") or (bone == "hips" and z > 0.98):
        collar = bone == "chest" and z > 1.38 and normal.y < 0.2
        return (SHIRT, CLOTH) if collar else (JERKIN, LEATHER)
    if bone == "hips" and z > 0.94:
        return (0.05, 0.03, 0.015), LEATHER
    return TROUSERS, CLOTH


def guard():
    # On guard: left foot forward, sword held out in front, point up.
    turns = {
        "hips": [("Z", -0.35)],
        "spine": [("Z", 0.1)],
        "chest": [("Z", 0.1)],
        "neck": [("Z", -0.15)],
        "thigh.L": [("X", -0.35), ("Y", -0.1)],
        "shin.L": [("X", 0.35)],
        "foot.L": [("X", 0.0)],
        "thigh.R": [("X", 0.2), ("Y", 0.12)],
        "shin.R": [("X", 0.3)],
        "foot.R": [("X", -0.2), ("Z", -0.4)],
        "upper_arm.R": [("X", -0.55), ("Y", -0.1)],
        "forearm.R": [("X", -1.0)],
        "hand.R": [("X", -0.2)],
        "upper_arm.L": [("X", -0.4), ("Y", -0.35)],
        "forearm.L": [("X", -1.3)],
    }
    return turns


def windup():
    # The sword drawn back high over the right shoulder, body coiled.
    turns = guard()
    turns["hips"] = [("Z", -0.55)]
    turns["spine"] = [("Z", -0.25), ("X", -0.05)]
    turns["chest"] = [("Z", -0.25)]
    turns["neck"] = [("Z", 0.45)]
    turns["upper_arm.R"] = [("Y", 0.9), ("X", -2.1)]
    turns["forearm.R"] = [("X", -1.6)]
    turns["hand.R"] = [("X", 0.6)]
    turns["upper_arm.L"] = [("X", -1.1), ("Y", -0.6)]
    turns["forearm.L"] = [("X", -0.6)]
    return turns


def slash():
    # The cut: a diagonal stroke from high right to low left, the body
    # uncoiling behind it and the weight driving onto the front foot.
    turns = guard()
    turns["hips"] = [("Z", 0.35)]
    turns["spine"] = [("Z", 0.35), ("X", 0.25)]
    turns["chest"] = [("Z", 0.25), ("X", 0.1)]
    turns["neck"] = [("Z", -0.55), ("X", -0.1)]
    turns["thigh.L"] = [("X", -0.6), ("Y", -0.15)]
    turns["shin.L"] = [("X", 0.6)]
    turns["thigh.R"] = [("X", 0.35), ("Y", 0.15)]
    turns["foot.R"] = [("X", -0.5), ("Z", -0.4)]
    turns["upper_arm.R"] = [("Y", -0.7), ("X", -0.7)]
    turns["forearm.R"] = [("X", -0.15)]
    # The wrist rolls through, so the blade follows the arm down.
    turns["hand.R"] = [("X", 1.3), ("Z", 0.4)]
    turns["upper_arm.L"] = [("X", 0.3), ("Y", -0.7)]
    turns["forearm.L"] = [("X", -0.4)]
    return turns


def breathe(t):
    b = math.sin(2 * math.pi * 0.6 * t)
    return {"chest": [("X", 0.015 * b)], "upper_arm.R": [("X", 0.02 * b)]}


KEYS = [
    (0.0, guard(), (0, 0, -0.03), "smooth"),
    (1.3, guard(), (0, 0, -0.03), "smooth"),
    (2.2, windup(), (0, 0.04, -0.02), "smooth"),
    (2.5, windup(), (0, 0.04, -0.02), "smooth"),
    (2.75, slash(), (0, -0.2, -0.1), "snap"),
    (3.2, slash(), (0, -0.2, -0.1), "smooth"),
    (4.3, guard(), (0, -0.15, -0.03), "smooth"),
    (5.0, guard(), (0, -0.15, -0.03), "smooth"),
]


def add_sword(rig, anatomy):
    # An arming sword in the right fist: steel blade with a fuller, a crossguard,
    # a leather-wrapped grip and a pommel. Held so the blade runs on from the
    # fist across the hand, forward and a little up.
    k = anatomy.k
    j = anatomy.joints
    grip = j["wrist.R"].lerp(j["knuckles.R"], 0.75)
    forward = Vector((0, -1.0, 0.25)).normalized()
    steel = metal_material("Blade", (0.75, 0.76, 0.78), roughness=0.12)
    gilt = metal_material("Guard", (0.55, 0.42, 0.2), roughness=0.3, brushed=False)
    wrap = leather_material("Grip", (0.07, 0.035, 0.015))
    parts = []
    blade = []
    for t in (0.0, 0.3, 0.6, 0.85, 1.0):
        blade.append(grip + forward * ((0.1 + 0.78 * t) * k))
    # A flat, tapering blade: a squashed tube, wide across, thin through.
    parts.append(add_tube("Blade", blade, [0.024 * k, 0.022 * k, 0.019 * k, 0.012 * k, 0.001 * k], steel, sides=4))
    side = Vector((1, 0, 0))
    flat = forward.cross(side)
    for vertex in parts[-1].data.vertices:
        # Squash the tube through its thickness, leaving a diamond section.
        vertex.co -= flat * ((vertex.co - grip).dot(flat) * 0.82)
    parts.append(add_tube("Crossguard", [grip + forward * 0.095 * k - side * 0.11 * k, grip + forward * 0.095 * k + side * 0.11 * k],
                          [0.012 * k, 0.012 * k], gilt, sides=8))
    parts.append(add_tube("Grip", [grip - forward * 0.08 * k, grip + forward * 0.09 * k], [0.016 * k, 0.017 * k], wrap, sides=10))
    parts.append(add_tube("Pommel", [grip - forward * 0.11 * k, grip - forward * 0.08 * k], [0.028 * k, 0.026 * k], gilt, sides=12))
    for part in parts:
        rigid(part, rig, "hand.R")
    return parts


def camera_path(t, position):
    # Alongside and ahead while walking; for the cut, a low three-quarter view.
    near = smootherstep((t + 0.5) / 1.5)
    walking = (position + Vector((-2.6, -3.9, 1.5)), position + Vector((0, 0, 1.0)))
    cutting = (position + Vector((-2.9, -2.9, 1.1)), position + Vector((0, -0.3, 1.05)))
    return walking[0].lerp(cutting[0], near), walking[1].lerp(cutting[1], near)


def basicswordsman():
    setup_stage(sun_elevation=28, sun_rotation=-140, sun_energy=4.0, sky_strength=0.25)
    anatomy = Anatomy(height=1.82, build=1.05)
    rig, _ = build_person("Swordsman", anatomy, outfit)
    add_head(rig, anatomy, TONE, hair=(0.08, 0.045, 0.02), hair_style="short", beard=(0.07, 0.04, 0.02))
    add_sword(rig, anatomy)
    distance = animate(rig, KEYS, walk_speed=1.1, walk_rate=0.9, camera_path=camera_path, lens=40, fstop=4.0, idle=breathe)
    add_meadow(distance, blades=60000, height=(0.05, 0.16))
