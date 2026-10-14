from modules.nature import setup_stage, add_meadow
from modules.body import lerp, smootherstep
from modules.bird import Anatomy, build_bird, add_feather_wind, animate

ANATOMY = dict(
    length=0.085, radius=0.03, head=0.02, neck=0.012,
    beak=(0.012, 0.0055, 0.002),
    legs=(0.02, 0.0013, 0.013),
    tail=(0.055, 0.04),
    wing=(0.02, 0.028, 0.03, 0.05),
)

CROWN = (0.2, 0.2, 0.21)
CHESTNUT = (0.3, 0.12, 0.04)
CHEEK = (0.45, 0.45, 0.42)
BIB = (0.018, 0.016, 0.015)
BELLY = (0.24, 0.235, 0.22)
BACK = (0.3, 0.16, 0.07)
BUFF = (0.45, 0.33, 0.18)
DARK = (0.06, 0.04, 0.03)


def mix(a, b, factor):
    return tuple(lerp(x, y, factor) for x, y in zip(a, b))


def coat(position, normal, bone):
    # A male house sparrow: grey crown, chestnut nape, pale cheeks and a
    # black bib; brown back streaked black with buff fringes; grey underparts.
    top = smootherstep((normal.z + 0.05) / 0.5)
    front = smootherstep((-normal.y - 0.2) / 0.4)
    if bone == "head":
        side = smootherstep((abs(normal.x) - 0.4) / 0.3)
        nape = smootherstep((normal.y + 0.1) / 0.4)
        color = mix(mix(CROWN, CHEEK, side * (1 - top)), CHESTNUT, nape * (1 - top) + 0.6 * side * top)
        throat = smootherstep((-normal.z - 0.2) / 0.3)
        return mix(color, BIB, throat), mix(color, BIB, throat), 0.0, 0.005
    if bone == "neck":
        color = mix(mix(BELLY, BIB, front), CHESTNUT, top)
        return color, color, 0.0, 0.008
    color = mix(BELLY, BACK, top)
    bib = front * smootherstep((position.z - 0.045) / 0.01) * smootherstep((0.016 - abs(position.x)) / 0.006)
    color = mix(color, BIB, bib)
    edge = mix(color, BUFF, top)
    return color, edge, top, 0.011 if top > 0.5 else 0.009


def palette(kind, index):
    # (colour, fringe, streak) for the flight, tail and covert feathers.
    if kind == "primary":
        return DARK, BUFF, 0.0
    if kind == "secondary":
        return DARK, CHESTNUT, 0.0
    if kind == "tertial":
        return BACK, BUFF, 1.0
    if kind == "covert":
        # The white wing bar.
        return CHESTNUT, (0.75, 0.73, 0.68), 0.3
    if kind == "lesser":
        return CHESTNUT, CHESTNUT, 0.0
    if kind == "tail":
        return (0.16, 0.11, 0.07), BUFF, 0.0
    return (0.3, 0.25, 0.2), (0.4, 0.33, 0.25), 0.0


def basicsparrow():
    setup_stage(sun_elevation=30, sun_rotation=-110, sun_energy=4.5, sky_strength=0.2)
    anatomy = Anatomy(**ANATOMY)
    rig, fly, opened, folded, flappers = build_bird("Sparrow", anatomy, coat, palette, beak_color=(0.03, 0.03, 0.035),
                                                    leg_color=(0.35, 0.22, 0.17))
    add_feather_wind(flappers, anatomy.wing[3])
    distance = animate(rig, fly, opened, folded, flappers, walk_speed=0.25, walk_rate=1.6, fly_speed=5.0, flap_rate=6.0,
                       beat=0.9, altitude=1.2, camera_distance=0.5, camera_height=0.1, camera_lift=-0.15)
    add_meadow(distance, blades=120000, height=(0.012, 0.04), near=0.25, falloff=0.6, spread=(-0.8, 6.0), strength=0.03)
