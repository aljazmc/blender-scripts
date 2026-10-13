import math

from modules.creature import (
    SIDES,
    add_armature,
    add_blob,
    add_material,
    add_ramp_material,
    add_segment,
    animate_creature,
    join_parts,
    leg_turns,
    setup_stage,
    skin,
)

LEGS = (("F", -0.65), ("B", 0.7))
RAINBOW = (
    (1.0, 0.1, 0.15),
    (1.0, 0.45, 0.05),
    (1.0, 0.85, 0.1),
    (0.2, 0.9, 0.3),
    (0.15, 0.45, 1.0),
    (0.6, 0.2, 1.0),
)
WALK = 2 * math.pi * 1.2
GALLOP = 2 * math.pi * 1.8
TROT = {"F.L": 0.0, "B.R": 0.0, "F.R": math.pi, "B.L": math.pi}
SKY_GALLOP = {"F.L": 0.0, "F.R": 0.5, "B.L": math.pi, "B.R": math.pi + 0.5}


def unicorn_bones():
    bones = [
        ("spine", (0, 0.9, 1.65), (0, -0.85, 1.75), None),
        ("neck.1", (0, -0.85, 1.75), (0, -1.15, 2.25), "spine"),
        ("neck.2", (0, -1.15, 2.25), (0, -1.35, 2.7), "neck.1"),
        ("head", (0, -1.35, 2.7), (0, -1.95, 2.55), "neck.2"),
        ("horn", (0, -1.6, 2.85), (0, -1.88, 3.5), "head"),
        ("tail.1", (0, 1.0, 1.85), (0, 1.35, 1.7), "spine"),
        ("tail.2", (0, 1.35, 1.7), (0, 1.6, 1.3), "tail.1"),
        ("tail.3", (0, 1.6, 1.3), (0, 1.75, 0.85), "tail.2"),
    ]
    for side, s in SIDES:
        x = 0.3 * s
        bones.append((f"ear.{side}", (0.1 * s, -1.43, 2.83), (0.14 * s, -1.41, 3.1), "head"))
        for leg, y in LEGS:
            bones += [
                (f"thigh.{leg}.{side}", (x, y, 1.45), (x, y, 0.95), "spine"),
                (f"shin.{leg}.{side}", (x, y, 0.95), (x, y + 0.03, 0.45), f"thigh.{leg}.{side}"),
                (f"foot.{leg}.{side}", (x, y + 0.03, 0.45), (x, y - 0.03, 0.08), f"shin.{leg}.{side}"),
            ]
    return bones


def build_unicorn():
    coat = add_ramp_material(
        "Coat", "ShaderNodeLayerWeight", "Facing",
        ((0.0, (1.0, 1.0, 1.0)), (0.5, (1.0, 0.8, 0.95)), (0.75, (0.7, 0.85, 1.0)), (1.0, (0.85, 0.7, 1.0))),
        roughness=0.35,
    )
    horn = add_ramp_material(
        "Horn", "ShaderNodeTexWave", "Fac",
        ((0.0, (1.0, 0.7, 0.15)), (1.0, (1.0, 0.95, 0.7))),
        roughness=0.25, metallic=0.3,
        settings={"wave_type": 'BANDS', "bands_direction": 'Z', "Scale": 60.0},
    )
    hoof = add_material("Hoof", (1.0, 0.7, 0.2), roughness=0.25, metallic=0.3)
    eye = add_material("Eye", (0.05, 0.05, 0.25), roughness=0.1)
    rainbow = [add_material(f"Rainbow.{i}", color, roughness=0.4, emission=0.3) for i, color in enumerate(RAINBOW)]

    parts = []
    add_segment(parts, "spine", (0, 1.05, 1.7), (0, -0.95, 1.78), 0.42, 0.46, coat, vertices=8)
    add_blob(parts, "spine", (0, 0.65, 1.68), (0.46, 0.5, 0.45), coat)
    add_blob(parts, "spine", (0, -0.6, 1.72), (0.46, 0.5, 0.5), coat)
    add_segment(parts, "neck.1", (0, -0.8, 1.8), (0, -1.17, 2.3), 0.32, 0.26, coat)
    add_segment(parts, "neck.2", (0, -1.15, 2.25), (0, -1.37, 2.75), 0.26, 0.2, coat)
    add_segment(parts, "head", (0, -1.3, 2.75), (0, -1.98, 2.5), 0.22, 0.14, coat)
    add_blob(parts, "head", (0, -1.9, 2.5), (0.15, 0.14, 0.13), coat)
    add_segment(parts, "horn", (0, -1.6, 2.85), (0, -1.88, 3.5), 0.07, 0.0, horn, vertices=8)

    # Rainbow mane along the back of the neck.
    for i in range(6):
        f = i / 5
        base = (0, -0.59 - 0.57 * f, 1.93 + 0.95 * f)
        add_segment(parts, "neck.1" if i < 3 else "neck.2", base, (0, base[1] + 0.3, base[2] - 0.05), 0.13, 0.0, rainbow[i], vertices=4)

    # Rainbow tail: two strands per tail bone.
    points = ((1.0, 1.85), (1.35, 1.7), (1.6, 1.3), (1.75, 0.85), (1.8, 0.45))
    bones = ("tail.1", "tail.2", "tail.3", "tail.3")
    radii = (0.08, 0.14, 0.18, 0.16, 0.0)
    for i, bone in enumerate(bones):
        for j, dx in enumerate((-0.05, 0.05)):
            start = (dx, *points[i])
            end = (dx, *points[i + 1])
            add_segment(parts, bone, start, end, radii[i], radii[i + 1], rainbow[(2 * i + j) % 6], vertices=5)

    for side, s in SIDES:
        x = 0.3 * s
        add_segment(parts, f"ear.{side}", (0.1 * s, -1.43, 2.83), (0.14 * s, -1.41, 3.1), 0.07, 0.0, coat, vertices=4)
        add_blob(parts, "head", (0.17 * s, -1.55, 2.72), (0.05, 0.05, 0.05), eye, segments=6, rings=4)
        for leg, y in LEGS:
            thigh = 0.17 if leg == "F" else 0.22
            add_segment(parts, f"thigh.{leg}.{side}", (x, y, 1.6), (x, y, 0.95), thigh, 0.11, coat)
            add_segment(parts, f"shin.{leg}.{side}", (x, y, 0.97), (x, y + 0.03, 0.45), 0.1, 0.08, coat)
            add_segment(parts, f"foot.{leg}.{side}", (x, y + 0.03, 0.47), (x, y - 0.03, 0.12), 0.08, 0.09, coat)
            add_segment(parts, f"foot.{leg}.{side}", (x, y - 0.03, 0.14), (x, y - 0.03, 0.0), 0.1, 0.12, hoof)

    return join_parts(parts, "Unicorn")


def tail_turns(phase, lift):
    return {
        f"tail.{i}": [("X", lift if i == 1 else 0.1), ("Z", 0.15 * i * math.sin(phase - 0.6 * i))]
        for i in (1, 2, 3)
    }


def walk(t):
    p = WALK * t
    turns = {
        "spine": [("Y", 0.03 * math.sin(p))],
        "neck.1": [("X", 0.06 * math.sin(2 * p))],
        "head": [("X", -0.05 * math.sin(2 * p))],
        "ear.L": [("X", 0.1 * math.sin(p))],
        "ear.R": [("X", 0.1 * math.sin(p + 1))],
    }
    turns.update(tail_turns(p, 0.2))
    for name, phase in TROT.items():
        turns.update(leg_turns(name, p + phase, swing=0.35, lift=0.7))
    return turns, 0.04 * math.sin(2 * p)


def fly(t):
    # No wings: it gallops through the air.
    p = GALLOP * t
    turns = {
        "neck.1": [("X", 0.25 + 0.08 * math.sin(p))],
        "head": [("X", -0.15)],
        "ear.L": [("X", -0.5)],
        "ear.R": [("X", -0.5)],
    }
    turns.update(tail_turns(p, 0.8))
    for name, phase in SKY_GALLOP.items():
        turns.update(leg_turns(name, p + phase, swing=0.6, lift=1.0))
    return turns, 0.15 * math.sin(p)


def basicunicorn():
    setup_stage()
    rig = add_armature("UnicornRig", unicorn_bones())
    skin(build_unicorn(), rig)
    # Without wings to show off, the camera stays low and looks up at it in flight.
    animate_creature(rig, walk, fly, walk_speed=1.5, fly_speed=5.0, altitude=4.0, camera_distance=8.0, camera_height=1.8, camera_lift=-2.0)
