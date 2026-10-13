import math

from modules.creature import (
    SIDES,
    add_armature,
    add_blob,
    add_material,
    add_panel,
    add_ramp_material,
    add_segment,
    animate_creature,
    join_parts,
    leg_turns,
    mirror,
    setup_stage,
    skin,
)

STRIDE = 2 * math.pi * 0.9
FLAP = 2 * math.pi * 0.9
# Four-beat walk: each leg a quarter cycle after the last.
WALK = {"B.L": 0.0, "F.L": math.pi / 2, "B.R": math.pi, "F.R": 3 * math.pi / 2}
# Leg joints (hip, knee, ankle, toe) for the left side; front legs at -Y.
LEGS = {
    "F": ((0.5, -0.75, 1.5), (0.55, -0.7, 0.9), (0.55, -0.8, 0.35), (0.55, -1.0, 0.05)),
    "B": ((0.5, 0.85, 1.45), (0.6, 0.65, 0.85), (0.6, 0.95, 0.35), (0.6, 0.75, 0.05)),
}
NECK = ((0, -1.0, 1.8), (0, -1.4, 2.3), (0, -1.7, 2.8), (0, -1.95, 3.2))
TAIL = ((0, 1.1, 1.6), (0, 1.7, 1.45), (0, 2.3, 1.2), (0, 2.9, 1.0), (0, 3.5, 0.85), (0, 4.0, 0.8))
# Wing joints (shoulder, elbow, wrist, tip) and membrane trailing edge, left side.
WING = ((0.35, -0.6, 2.15), (1.5, -0.5, 2.6), (2.9, -0.15, 2.45), (4.1, 0.5, 2.2))
TRAILING = ((0.4, 0.7, 1.95), (1.6, 1.1, 2.1), (2.9, 1.3, 2.1))


def dragon_bones():
    bones = [("spine", (0, 1.1, 1.6), (0, -1.0, 1.8), None)]
    parent = "spine"
    for i in range(3):
        bones.append((f"neck.{i + 1}", NECK[i], NECK[i + 1], parent))
        parent = f"neck.{i + 1}"
    bones += [
        ("head", NECK[3], (0, -2.65, 3.15), "neck.3"),
        ("jaw", (0, -2.05, 3.05), (0, -2.6, 2.95), "head"),
    ]
    parent = "spine"
    for i in range(5):
        bones.append((f"tail.{i + 1}", TAIL[i], TAIL[i + 1], parent))
        parent = f"tail.{i + 1}"
    for side, s in SIDES:
        bones.append((f"horn.{side}", (0.18 * s, -2.05, 3.4), (0.3 * s, -1.6, 3.8), "head"))
        for leg, (hip, knee, ankle, toe) in LEGS.items():
            hip, knee, ankle, toe = mirror((hip, knee, ankle, toe), s)
            bones += [
                (f"thigh.{leg}.{side}", hip, knee, "spine"),
                (f"shin.{leg}.{side}", knee, ankle, f"thigh.{leg}.{side}"),
                (f"foot.{leg}.{side}", ankle, toe, f"shin.{leg}.{side}"),
            ]
        joints = mirror(WING, s)
        parent = "spine"
        for i in range(3):
            bones.append((f"wing.{i + 1}.{side}", joints[i], joints[i + 1], parent))
            parent = f"wing.{i + 1}.{side}"
    return bones


def build_dragon():
    scales = add_ramp_material(
        "Scales", "ShaderNodeTexVoronoi", "Distance",
        ((0.0, (0.0, 0.2, 0.1)), (0.4, (0.0, 0.65, 0.3)), (1.0, (0.45, 1.0, 0.55))),
        roughness=0.35, metallic=0.2,
        settings={"feature": 'F1', "Scale": 40.0},
    )
    belly = add_ramp_material(
        "Belly", "ShaderNodeTexWave", "Fac",
        ((0.0, (0.85, 0.35, 0.02)), (1.0, (1.0, 0.75, 0.1))),
        roughness=0.4,
        settings={"wave_type": 'BANDS', "bands_direction": 'Y', "Scale": 25.0},
    )
    membrane = add_ramp_material(
        "Membrane", "ShaderNodeTexWave", "Fac",
        ((0.0, (0.55, 0.0, 0.12)), (1.0, (1.0, 0.1, 0.5))),
        roughness=0.5,
        settings={"wave_type": 'BANDS', "bands_direction": 'X', "Scale": 8.0, "Distortion": 4.0},
    )
    ivory = add_material("Ivory", (0.95, 0.9, 0.75), roughness=0.4)
    claw = add_material("Claw", (0.03, 0.03, 0.03), roughness=0.2)
    eye = add_material("Eye", (1.0, 0.8, 0.0), roughness=0.1, emission=8.0)

    parts = []
    add_segment(parts, "spine", (0, 1.2, 1.6), (0, -1.1, 1.8), 0.55, 0.6, scales, vertices=8)
    add_blob(parts, "spine", (0, 0.0, 1.45), (0.5, 1.0, 0.45), belly)
    for y in (0.9, 0.5, 0.1, -0.3, -0.7):
        add_segment(parts, "spine", (0, y, 2.1), (0, y + 0.2, 2.5), 0.12, 0.0, ivory, vertices=4)

    neck_radii = (0.4, 0.32, 0.27, 0.24)
    for i in range(3):
        add_segment(parts, f"neck.{i + 1}", NECK[i], NECK[i + 1], neck_radii[i], neck_radii[i + 1], scales)
        top = (NECK[i][0], NECK[i][1] + 0.05, NECK[i][2] + neck_radii[i] - 0.05)
        add_segment(parts, f"neck.{i + 1}", top, (0, top[1] + 0.2, top[2] + 0.25), 0.08, 0.0, ivory, vertices=4)
    add_segment(parts, "head", (0, -1.85, 3.25), (0, -2.7, 3.15), 0.28, 0.15, scales)
    add_segment(parts, "jaw", (0, -2.0, 3.05), (0, -2.62, 2.95), 0.17, 0.08, belly)

    tail_radii = (0.45, 0.35, 0.27, 0.2, 0.13, 0.05)
    for i in range(5):
        add_segment(parts, f"tail.{i + 1}", TAIL[i], TAIL[i + 1], tail_radii[i], tail_radii[i + 1], scales)
        top = (0, TAIL[i][1] + 0.2, TAIL[i][2] + tail_radii[i] - 0.05)
        add_segment(parts, f"tail.{i + 1}", top, (0, top[1] + 0.2, top[2] + 0.25 * tail_radii[i] / 0.45), 0.08, 0.0, ivory, vertices=4)
    add_panel(parts, "tail.5", [(0, 3.9, 0.8), (0.3, 4.2, 0.8), (0, 4.6, 0.8), (-0.3, 4.2, 0.8)], membrane)

    for side, s in SIDES:
        add_segment(parts, f"horn.{side}", (0.18 * s, -2.05, 3.4), (0.3 * s, -1.6, 3.8), 0.08, 0.0, ivory)
        add_blob(parts, "head", (0.2 * s, -2.15, 3.35), (0.06, 0.06, 0.06), eye, segments=6, rings=4)
        for leg, joints in LEGS.items():
            hip, knee, ankle, toe = mirror(joints, s)
            thigh = 0.28 if leg == "F" else 0.33
            add_segment(parts, f"thigh.{leg}.{side}", hip, knee, thigh, 0.18, scales)
            add_segment(parts, f"shin.{leg}.{side}", knee, ankle, 0.15, 0.11, scales)
            add_segment(parts, f"foot.{leg}.{side}", ankle, toe, 0.12, 0.1, scales)
            for dx in (-0.08, 0.0, 0.08):
                add_segment(parts, f"foot.{leg}.{side}", (toe[0] + dx, toe[1], 0.05), (toe[0] + dx * 1.5, toe[1] - 0.3, 0.0), 0.05, 0.0, claw, vertices=4)

        # Wing arm, then one membrane panel per wing bone.
        shoulder, elbow, wrist, tip = mirror(WING, s)
        back, middle, outer = mirror(TRAILING, s)
        add_segment(parts, f"wing.1.{side}", shoulder, elbow, 0.12, 0.09, scales)
        add_segment(parts, f"wing.2.{side}", elbow, wrist, 0.09, 0.06, scales)
        add_segment(parts, f"wing.3.{side}", wrist, tip, 0.06, 0.02, scales)
        add_panel(parts, f"wing.1.{side}", [shoulder, elbow, middle, back], membrane)
        add_panel(parts, f"wing.2.{side}", [elbow, wrist, outer, middle], membrane)
        add_panel(parts, f"wing.3.{side}", [wrist, tip, outer], membrane)

    return join_parts(parts, "Dragon")


def walk(t):
    p = STRIDE * t
    turns = {
        "spine": [("Y", 0.03 * math.sin(p)), ("Z", 0.04 * math.sin(p))],
        "neck.1": [("Z", 0.08 * math.sin(p))],
        "neck.2": [("Z", 0.06 * math.sin(p - 0.5))],
        "head": [("X", 0.05 * math.sin(2 * p))],
        "jaw": [("X", 0.1 + 0.05 * math.sin(3 * p))],
    }
    for i in range(1, 6):
        turns[f"tail.{i}"] = [("Z", 0.12 * math.sin(p - 0.5 * i))]
    # Wings half raised and swept back, swaying with each step.
    for side, s in SIDES:
        turns[f"wing.1.{side}"] = [("Z", s * 0.9), ("Y", -s * (0.6 + 0.05 * math.sin(p)))]
        turns[f"wing.2.{side}"] = [("Z", -s * 0.5)]
        turns[f"wing.3.{side}"] = [("Z", s * 0.3)]
    for name, phase in WALK.items():
        turns.update(leg_turns(name, p + phase, swing=0.3, lift=0.5))
    return turns, 0.05 * math.sin(2 * p)


def fly(t):
    p = FLAP * t
    turns = {
        "neck.1": [("X", 0.35)],
        "neck.2": [("X", 0.25)],
        "neck.3": [("X", 0.15)],
        "head": [("X", -0.5)],
        "jaw": [("X", 0.25 + 0.1 * math.sin(p))],
    }
    # The tail lifts level and undulates behind.
    turns["tail.1"] = [("X", 0.25), ("Z", 0.1 * math.sin(0.5 * p - 0.6))]
    for i in range(2, 6):
        turns[f"tail.{i}"] = [("X", 0.05), ("Z", 0.1 * math.sin(0.5 * p - 0.6 * i))]
    for side, s in SIDES:
        turns[f"wing.1.{side}"] = [("Y", -s * 0.7 * math.sin(p)), ("Z", s * 0.15 * math.cos(p))]
        turns[f"wing.2.{side}"] = [("Y", -s * 0.35 * math.sin(p - 0.7))]
        turns[f"wing.3.{side}"] = [("Y", -s * 0.4 * math.sin(p - 1.4))]
        # Front legs tucked under the chest, hind legs trailing.
        turns[f"thigh.F.{side}"] = [("X", 0.7)]
        turns[f"shin.F.{side}"] = [("X", -1.4)]
        turns[f"foot.F.{side}"] = [("X", 0.6)]
        turns[f"thigh.B.{side}"] = [("X", 1.2)]
        turns[f"shin.B.{side}"] = [("X", 0.4)]
        turns[f"foot.B.{side}"] = [("X", 0.6)]
    return turns, -0.25 * math.sin(p)


def basicdragon():
    setup_stage()
    rig = add_armature("DragonRig", dragon_bones())
    skin(build_dragon(), rig)
    # End behind and above it, so the wingspan spreads across the frame.
    animate_creature(rig, walk, fly, walk_speed=1.2, fly_speed=6.0, altitude=5.0, camera_distance=14.0, camera_height=3.0, camera_lift=4.0, camera_sweep=(200, 115))
