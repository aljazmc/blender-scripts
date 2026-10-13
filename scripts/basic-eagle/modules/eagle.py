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

HOP = 2 * math.pi * 1.6
FLAP = 2 * math.pi * 1.4


def eagle_bones():
    bones = [
        ("spine", (0, 0.35, 1.05), (0, -0.35, 1.15), None),
        ("neck", (0, -0.35, 1.15), (0, -0.5, 1.4), "spine"),
        ("head", (0, -0.5, 1.4), (0, -0.8, 1.42), "neck"),
        ("tail", (0, 0.35, 1.05), (0, 0.85, 1.0), "spine"),
    ]
    for side, s in SIDES:
        x = 0.16 * s
        bones += [
            (f"thigh.{side}", (x, 0.05, 0.95), (x, 0.12, 0.55), "spine"),
            (f"shin.{side}", (x, 0.12, 0.55), (x, 0.02, 0.14), f"thigh.{side}"),
            (f"foot.{side}", (x, 0.02, 0.14), (x, -0.15, 0.03), f"shin.{side}"),
            (f"wing.1.{side}", (0.28 * s, -0.15, 1.2), (0.85 * s, -0.1, 1.22), "spine"),
            (f"wing.2.{side}", (0.85 * s, -0.1, 1.22), (1.45 * s, -0.05, 1.22), f"wing.1.{side}"),
            (f"wing.3.{side}", (1.45 * s, -0.05, 1.22), (2.05 * s, 0.05, 1.2), f"wing.2.{side}"),
        ]
    return bones


def build_eagle():
    feathers = add_ramp_material(
        "Feathers", "ShaderNodeTexWave", "Fac",
        ((0.0, (0.25, 0.08, 0.02)), (0.6, (0.6, 0.25, 0.04)), (1.0, (1.0, 0.65, 0.1))),
        roughness=0.6,
        settings={"wave_type": 'BANDS', "bands_direction": 'Y', "Scale": 25.0, "Distortion": 3.0},
    )
    primaries = add_ramp_material(
        "Primaries", "ShaderNodeTexWave", "Fac",
        ((0.0, (0.12, 0.04, 0.02)), (1.0, (0.95, 0.3, 0.03))),
        roughness=0.4, metallic=0.2,
        settings={"wave_type": 'BANDS', "bands_direction": 'X', "Scale": 15.0},
    )
    white = add_ramp_material(
        "White", "ShaderNodeTexNoise", "Fac",
        ((0.3, (0.85, 0.88, 0.95)), (0.7, (1.0, 1.0, 1.0))),
        settings={"Scale": 30.0},
    )
    beak = add_material("Beak", (1.0, 0.65, 0.0), roughness=0.3)
    talon = add_material("Talon", (0.05, 0.05, 0.05), roughness=0.2)
    eye = add_material("Eye", (1.0, 0.55, 0.0), roughness=0.1, emission=2.0)

    parts = []
    add_blob(parts, "spine", (0, 0.0, 1.08), (0.33, 0.52, 0.32), feathers)
    add_segment(parts, "spine", (0, 0.3, 1.05), (0, 0.55, 1.02), 0.25, 0.12, feathers)
    add_segment(parts, "neck", (0, -0.3, 1.15), (0, -0.52, 1.42), 0.2, 0.16, white)
    add_blob(parts, "head", (0, -0.63, 1.45), (0.16, 0.22, 0.16), white)
    add_segment(parts, "head", (0, -0.78, 1.45), (0, -0.98, 1.37), 0.07, 0.0, beak, vertices=5)
    add_panel(parts, "tail", [(-0.1, 0.4, 1.05), (0.1, 0.4, 1.05), (0.3, 0.95, 1.0), (0.12, 1.02, 1.0), (-0.12, 1.02, 1.0), (-0.3, 0.95, 1.0)], white)

    for side, s in SIDES:
        x = 0.16 * s
        add_blob(parts, "head", (0.12 * s, -0.7, 1.5), (0.035, 0.035, 0.035), eye, segments=6, rings=4)
        add_segment(parts, f"thigh.{side}", (x, 0.05, 0.98), (x, 0.12, 0.55), 0.11, 0.07, feathers)
        add_segment(parts, f"shin.{side}", (x, 0.12, 0.57), (x, 0.02, 0.12), 0.04, 0.035, beak)
        for dx in (-0.06, 0.0, 0.06):
            add_segment(parts, f"foot.{side}", (x, 0.02, 0.06), (x + dx * s, -0.2, 0.02), 0.025, 0.0, beak, vertices=4)
        add_segment(parts, f"foot.{side}", (x, 0.02, 0.06), (x, 0.15, 0.02), 0.02, 0.0, talon, vertices=4)

        add_panel(parts, f"wing.1.{side}", mirror(((0.25, -0.18, 1.2), (0.85, -0.14, 1.22), (0.85, 0.45, 1.2), (0.25, 0.4, 1.18)), s), feathers)
        add_panel(parts, f"wing.2.{side}", mirror(((0.85, -0.14, 1.22), (1.45, -0.09, 1.22), (1.45, 0.45, 1.2), (0.85, 0.45, 1.2)), s), feathers)
        add_panel(parts, f"wing.3.{side}", mirror(((1.45, -0.09, 1.22), (2.05, 0.0, 1.2), (2.1, 0.3, 1.19), (1.45, 0.45, 1.2)), s), primaries)
        # Slotted primary feathers fanning out at the wing tip.
        for i in range(4):
            base = 1.6 + 0.13 * i
            feather = (
                (base, 0.05 + 0.08 * i, 1.2),
                (base + 0.08, 0.06 + 0.08 * i, 1.2),
                (base + 0.55 - 0.08 * i, 0.25 + 0.15 * i, 1.19),
                (base + 0.47 - 0.08 * i, 0.3 + 0.15 * i, 1.19),
            )
            add_panel(parts, f"wing.3.{side}", mirror(feather, s), primaries)

    return join_parts(parts, "Eagle")


def walk(t):
    p = HOP * t
    turns = {
        "spine": [("Y", 0.08 * math.sin(p))],
        "neck": [("X", 0.15 * math.sin(2 * p))],
        "head": [("X", -0.15 * math.sin(2 * p))],
        "tail": [("X", 0.1 * math.sin(2 * p))],
    }
    # Wings folded along the body.
    for side, s in SIDES:
        turns[f"wing.1.{side}"] = [("Z", s * 1.35), ("Y", s * 0.35)]
        turns[f"wing.2.{side}"] = [("Z", -s * 2.6)]
        turns[f"wing.3.{side}"] = [("Z", s * 2.4)]
    for side, phase in (("L", 0.0), ("R", math.pi)):
        turns.update(leg_turns(side, p + phase, swing=0.35, lift=0.6))
    return turns, 0.03 * abs(math.sin(p))


def fly(t):
    p = FLAP * t
    turns = {
        "neck": [("X", 0.2)],
        "head": [("X", -0.25)],
        "tail": [("X", 0.05 * math.sin(p))],
    }
    # Each wing section lags the one before it, so the beat ripples outwards.
    for side, s in SIDES:
        turns[f"wing.1.{side}"] = [("Y", -s * 0.55 * math.sin(p)), ("Z", s * 0.1 * math.cos(p))]
        turns[f"wing.2.{side}"] = [("Y", -s * 0.25 * math.sin(p - 0.6))]
        turns[f"wing.3.{side}"] = [("Y", -s * 0.3 * math.sin(p - 1.2))]
        turns[f"thigh.{side}"] = [("X", 1.1)]
        turns[f"shin.{side}"] = [("X", 0.4)]
        turns[f"foot.{side}"] = [("X", 0.8)]
    return turns, -0.12 * math.sin(p)


def basiceagle():
    setup_stage()
    rig = add_armature("EagleRig", eagle_bones())
    skin(build_eagle(), rig)
    # End behind and above it, so the wingspan spreads across the frame.
    animate_creature(rig, walk, fly, walk_speed=0.8, fly_speed=7.0, altitude=5.0, camera_distance=6.0, camera_height=1.2, camera_lift=2.5, camera_sweep=(200, 115))
