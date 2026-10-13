import random

from modules.landscape import (
    MeshBuilder,
    add_broadleaf,
    add_bush,
    add_conifer,
    add_flat_material,
    add_flower,
    add_mover,
    add_orbit_camera,
    add_rock,
    add_terrain,
    add_tuft,
    add_wind,
    hills,
    scatter,
    setup_stage,
    smoothstep,
)

CLEARING = 12
UNDERGROWTH = ((0.2, 0.5, 0.1), (0.3, 0.55, 0.08), (0.15, 0.4, 0.12))
AUTUMN = ((1.0, 0.45, 0.05), (0.95, 0.2, 0.05), (1.0, 0.75, 0.1))
FLOWERS = ((1.0, 0.85, 0.1), (0.9, 0.2, 0.8), (1.0, 1.0, 1.0))


def ground(x, y):
    return hills(x, y, 2.2, scale=0.04)


def ground_color(z, slope):
    if slope > 0.3:
        return (0.4, 0.3, 0.15)
    f = smoothstep(-1.5, 2.0, z)
    return (0.2 + 0.12 * f, 0.4 - 0.08 * f, 0.08 + 0.04 * f)


def basicforest():
    setup_stage()
    rng = random.Random(11)
    material = add_flat_material()

    land = MeshBuilder(rng)
    add_terrain(land, size=100, cells=64, height=ground, color=ground_color)
    for x, y in scatter(rng, 15, 40):
        add_rock(land, x, y, ground(x, y), rng.uniform(0.4, 1.0), rng)
    land.build("Terrain", material)

    # Trees ring a clearing, mostly conifers with a few autumn-coloured ones.
    plants = MeshBuilder(rng)
    for x, y in scatter(rng, 170, 45, keep=lambda x, y: x * x + y * y > CLEARING ** 2, spacing=2.6):
        z = ground(x, y)
        kind = rng.random()
        if kind < 0.55:
            add_conifer(plants, x, y, z, rng.uniform(0.9, 1.5), rng)
        elif kind < 0.9:
            add_broadleaf(plants, x, y, z, rng.uniform(0.9, 1.3), rng)
        else:
            add_broadleaf(plants, x, y, z, rng.uniform(0.9, 1.3), rng, palette=AUTUMN)
    for x, y in scatter(rng, 120, 40, keep=lambda x, y: x * x + y * y > 36):
        add_bush(plants, x, y, ground(x, y), rng.uniform(0.4, 0.8), rng.choice(UNDERGROWTH), rng)
    for x, y in scatter(rng, 6000, 40):
        add_tuft(plants, x, y, ground(x, y), rng.uniform(0.3, 0.6), rng.choice(UNDERGROWTH), rng)
    for x, y in scatter(rng, 250, CLEARING):
        add_flower(plants, x, y, ground(x, y), rng.uniform(0.3, 0.5), rng.choice(FLOWERS), rng)
    plants = plants.build("Plants", material)

    gusts = add_mover("Gusts", (0.25, 0, 0))
    flutter = add_mover("Flutter", (0.4, 0.3, 0))
    add_wind(plants, gusts, flutter, strength=0.8)

    # From inside the clearing, looking across it at the forest edge.
    add_orbit_camera(target=(0, 0, ground(0, 0) + 2.5), distance=9, height=2.5, start=0, sweep=60)
