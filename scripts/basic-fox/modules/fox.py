from modules.nature import setup_stage, add_meadow
from modules.body import lerp, smootherstep
from modules.quadruped import Anatomy, build_animal, add_face, ear_material, animate

ANATOMY = dict(
    length=0.4, height=0.4, width=0.05,
    chest=0.095, waist=0.07, hips=0.075,
    neck=(0.12, 30, 0.075, 0.05),
    head=(0.07, 0.058),
    snout=(0.09, 0.017, 0.008),
    legs=(0.03, 0.013, 0.015),
    tail=(0.36, 0.028, 22),
    front=(0.56, 0.17), hind=(0.58, 0.27),
)
TAIL_TIP = Anatomy(**ANATOMY).joints["tail.3"]

RED = (0.42, 0.11, 0.025)
RUST = (0.3, 0.08, 0.02)
WHITE = (0.72, 0.68, 0.62)
BLACK = (0.025, 0.02, 0.018)


def mix(a, b, factor):
    return tuple(lerp(x, y, factor) for x, y in zip(a, b))


def coat(position, normal, bone):
    # Russet red, deeper along the back, with a white bib, belly and lower
    # jaw, black stockings and a long brush tipped in white.
    under = smootherstep((-normal.z - 0.3) / 0.4)
    top = smootherstep((normal.z - 0.2) / 0.5)
    if bone.startswith(("upper", "lower", "foot", "tail")):
        # Limbs and tail keep their own colours; no belly patch where they join.
        under = 0.0
    # Only the underside proper, not the folds where the legs meet the body.
    under *= smootherstep((0.68 * ANATOMY["height"] - position.z) / (0.08 * ANATOMY["height"]))
    color = mix(mix(RED, RUST, top), WHITE, under)
    length, tip = 0.03, 0.15 * top
    if bone == "neck":
        color, length = mix(RED, WHITE, smootherstep((-normal.z + 0.1) / 0.5)), 0.04
    elif bone in ("head", "snout"):
        jaw = smootherstep((-normal.z + 0.15) / 0.4)
        color = mix(RED, WHITE, jaw)
        length, tip = (0.008, 0.0) if bone == "snout" else (0.016, 0.0)
    elif bone.startswith("tail"):
        length, tip = 0.065, 0.4
        if bone == "tail.3" and position.y > TAIL_TIP.y - 0.07:
            color, tip = WHITE, 0.0
    elif bone.startswith(("lower", "foot")):
        color, length, tip = BLACK, 0.01, 0.0
    elif bone.startswith("upper"):
        color, length = mix(color, BLACK, 0.25), 0.022
    return color, length, tip


def basicfox():
    setup_stage(sun_elevation=22, sun_rotation=-110, sun_energy=4.5, sky_strength=0.2)
    anatomy = Anatomy(**ANATOMY)
    rig, bvh, grow_fur = build_animal("Fox", anatomy, coat, tip_color=(0.03, 0.02, 0.015),
                                            density=160000.0, radius=0.0004)
    features = add_face(rig, bvh, anatomy, ear_material((0.04, 0.03, 0.025), (0.6, 0.5, 0.45)),
                        ear_size=(0.085, 0.07), ear_spread=0.4, ear_tilt=0.15, eye_size=0.008)
    fur = grow_fur(features)
    distance = animate(rig, fur, walk_speed=1.0, run_speed=6.5, walk_rate=1.3, run_rate=3.0,
                       camera_distance=2.0, camera_height=0.4)
    add_meadow(distance)
