from modules.nature import setup_stage, add_meadow
from modules.body import lerp, smootherstep
from modules.bird import Anatomy, build_bird, add_feather_wind, animate

ANATOMY = dict(
    length=0.075, radius=0.032, head=0.021, neck=0.01,
    beak=(0.011, 0.0035, 0.002),
    legs=(0.026, 0.0012, 0.014),
    tail=(0.058, 0.04),
    wing=(0.019, 0.026, 0.03, 0.048),
)

ORANGE = (0.5, 0.17, 0.03)
BORDER = (0.22, 0.24, 0.26)
OLIVE = (0.16, 0.12, 0.06)
WHITE = (0.36, 0.35, 0.32)
BUFF = (0.32, 0.24, 0.12)


def mix(a, b, factor):
    return tuple(lerp(x, y, factor) for x, y in zip(a, b))


def coat(position, normal, bone):
    # A European robin: olive-brown above, an orange face and breast edged in
    # blue-grey, a white belly.
    top = smootherstep((normal.z + 0.05) / 0.5)
    front = smootherstep((-normal.y - 0.1) / 0.4)
    if bone == "head":
        face = front * (1 - smootherstep((normal.z - 0.35) / 0.3))
        color = mix(OLIVE, ORANGE, face)
        return color, color, 0.0, 0.005
    if bone == "neck":
        color = mix(mix(BORDER, OLIVE, top), ORANGE, front * (1 - top))
        return color, color, 0.0, 0.007
    breast = front * smootherstep((position.z - 0.044) / 0.008)
    color = mix(mix(WHITE, OLIVE, top), ORANGE, breast * (1 - top))
    # Blue-grey where the orange gives way.
    border = smootherstep(1 - 4 * abs(breast - 0.5)) * (1 - top)
    color = mix(color, BORDER, 0.6 * border)
    return color, mix(color, BUFF, 0.3 * top), 0.0, 0.009 if top > 0.5 else 0.008


def palette(kind, index):
    if kind in ("primary", "secondary"):
        return (0.08, 0.06, 0.035), BUFF, 0.0
    if kind == "tertial":
        return OLIVE, BUFF, 0.4
    if kind in ("covert", "lesser"):
        return OLIVE, (0.38, 0.3, 0.17) if kind == "covert" else OLIVE, 0.0
    return (0.12, 0.09, 0.05), OLIVE, 0.0


def basicrobin():
    setup_stage(sun_elevation=30, sun_rotation=-110, sun_energy=4.5, sky_strength=0.2)
    anatomy = Anatomy(**ANATOMY)
    rig, fly, opened, folded, flappers = build_bird("Robin", anatomy, coat, palette, beak_color=(0.03, 0.025, 0.02),
                                                    leg_color=(0.3, 0.2, 0.16))
    add_feather_wind(flappers, anatomy.wing[3])
    distance = animate(rig, fly, opened, folded, flappers, walk_speed=0.3, walk_rate=1.8, fly_speed=5.0, flap_rate=6.0,
                       beat=0.9, altitude=1.2, camera_distance=0.5, camera_height=0.1, camera_lift=-0.15)
    add_meadow(distance, blades=120000, height=(0.012, 0.04), near=0.25, falloff=0.6, spread=(-0.8, 6.0), strength=0.03)
