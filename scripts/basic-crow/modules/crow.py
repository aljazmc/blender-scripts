from modules.nature import setup_stage, add_meadow
from modules.body import smootherstep
from modules.bird import Anatomy, build_bird, add_feather_wind, animate

ANATOMY = dict(
    length=0.2, radius=0.062, head=0.038, neck=0.03,
    beak=(0.05, 0.012, 0.008),
    legs=(0.06, 0.004, 0.038),
    tail=(0.16, 0.12),
    wing=(0.065, 0.085, 0.1, 0.16),
)

BLACK = (0.012, 0.012, 0.014)
GLOSS = (0.022, 0.022, 0.028)


def coat(position, normal, bone):
    # Black all over; the thin-film sheen in the material does the rest.
    top = smootherstep((normal.z + 0.1) / 0.5)
    size = 0.011 if bone == "head" else 0.016 if bone == "neck" else 0.024
    return BLACK, GLOSS, 0.0, size * (0.8 + 0.2 * top)


def palette(kind, index):
    if kind in ("primary", "secondary", "tail"):
        return (0.01, 0.01, 0.012), GLOSS, 0.0
    return BLACK, GLOSS, 0.0


def basiccrow():
    setup_stage(sun_elevation=30, sun_rotation=-110, sun_energy=5.0, sky_strength=0.2)
    anatomy = Anatomy(**ANATOMY)
    rig, fly, opened, folded, flappers = build_bird("Crow", anatomy, coat, palette, beak_color=(0.015, 0.015, 0.017),
                                                    leg_color=(0.02, 0.02, 0.022), sheen=0.15, film=420.0)
    add_feather_wind(flappers, anatomy.wing[3])
    distance = animate(rig, fly, opened, folded, flappers, walk_speed=0.5, walk_rate=1.2, fly_speed=7.0, flap_rate=3.5,
                       beat=0.8, glide=0.6, altitude=2.0, camera_distance=1.2, camera_height=0.25, camera_lift=-0.3)
    add_meadow(distance, blades=120000, height=(0.02, 0.07), near=0.5, falloff=1.0, spread=(-1.5, 8.0), strength=0.05)
