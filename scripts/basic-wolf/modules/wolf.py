from modules.nature import setup_stage, add_meadow
from modules.body import lerp, smootherstep
from modules.quadruped import Anatomy, build_animal, add_face, ear_material, animate

ANATOMY = dict(
    length=0.75, height=0.8, width=0.09,
    chest=0.2, waist=0.13, hips=0.14,
    neck=(0.2, 28, 0.14, 0.085),
    head=(0.12, 0.1),
    snout=(0.12, 0.033, 0.015),
    legs=(0.062, 0.027, 0.028),
    tail=(0.45, 0.045, 48),
)

BACK = (0.1, 0.085, 0.07)
FLANK = (0.3, 0.25, 0.19)
CREAM = (0.55, 0.48, 0.38)
TAN = (0.3, 0.24, 0.17)


def mix(a, b, factor):
    return tuple(lerp(x, y, factor) for x, y in zip(a, b))


def coat(position, normal, bone):
    # Grizzled grey: a dark, black-tipped saddle, buff flanks, a cream belly,
    # throat and muzzle, tawny legs and a thick ruff and tail.
    under = smootherstep((-normal.z - 0.1) / 0.5)
    top = smootherstep((normal.z - 0.2) / 0.5)
    if bone.startswith(("upper", "lower", "foot", "tail")):
        # Limbs and tail keep their own colours; no belly patch where they join.
        under = 0.0
    # Only the underside proper, not the folds where the legs meet the body.
    under *= smootherstep((0.68 * ANATOMY["height"] - position.z) / (0.08 * ANATOMY["height"]))
    color = mix(mix(FLANK, BACK, top), CREAM, under)
    length, tip = 0.05, 0.3 + 0.6 * top
    if bone == "neck":
        length, color = 0.085, mix(color, CREAM, 0.3 * under)
    elif bone in ("head", "snout"):
        cheek = smootherstep((-normal.z + 0.2) / 0.6)
        color = mix(mix(FLANK, BACK, 0.4 * top), CREAM, cheek if bone == "snout" else 0.6 * cheek)
        length, tip = (0.012, 0.2) if bone == "snout" else (0.025, 0.4 * top)
    elif bone.startswith("tail"):
        length, tip = 0.09, 0.5 + 0.5 * top
        if bone == "tail.3":
            color, tip = BACK, 1.0
    elif bone.startswith(("lower", "foot")):
        color, length, tip = mix(TAN, CREAM, 0.3 * under), 0.015, 0.0
    elif bone.startswith("upper"):
        color, length = mix(color, TAN, 0.4), 0.035
    return color, length, tip


def basicwolf():
    setup_stage(sun_elevation=25, sun_rotation=-110, sun_energy=4.5, sky_strength=0.2)
    anatomy = Anatomy(**ANATOMY)
    rig, bvh, grow_fur = build_animal("Wolf", anatomy, coat, tip_color=(0.02, 0.018, 0.015))
    features = add_face(rig, bvh, anatomy, ear_material((0.2, 0.18, 0.16), (0.55, 0.47, 0.42)),
                        ear_size=(0.12, 0.1), ear_spread=0.45, ear_tilt=0.25)
    fur = grow_fur(features)
    distance = animate(rig, fur, walk_speed=1.3, run_speed=8.0, walk_rate=0.95, run_rate=2.6,
                       camera_distance=3.6, camera_height=0.7)
    add_meadow(distance)
