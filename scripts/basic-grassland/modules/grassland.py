import random

from modules.landscape import (
    MeshBuilder,
    add_broadleaf,
    add_bush,
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

GRASS = ((0.3, 0.75, 0.1), (0.45, 0.8, 0.1), (0.2, 0.6, 0.12), (0.6, 0.8, 0.15))
FLOWERS = ((1.0, 0.15, 0.1), (1.0, 0.85, 0.1), (0.9, 0.2, 0.8), (1.0, 1.0, 1.0), (0.3, 0.4, 1.0))


def ground(x, y):
    return hills(x, y, 1.2)


def ground_color(z, slope):
    if slope > 0.35:
        return (0.45, 0.35, 0.15)
    f = smoothstep(-1.0, 1.5, z)
    return (0.2 + 0.2 * f, 0.5 + 0.2 * f, 0.08 + 0.04 * f)


def basicgrassland():
    setup_stage()
    rng = random.Random(7)
    material = add_flat_material()

    land = MeshBuilder(rng)
    add_terrain(land, size=100, cells=64, height=ground, color=ground_color)
    for x, y in scatter(rng, 12, 40):
        add_rock(land, x, y, ground(x, y), rng.uniform(0.3, 0.8), rng)
    land.build("Terrain", material)

    plants = MeshBuilder(rng)
    for x, y in scatter(rng, 12000, 32):
        add_tuft(plants, x, y, ground(x, y), rng.uniform(0.35, 0.7), rng.choice(GRASS), rng)
    for x, y in scatter(rng, 700, 30):
        add_flower(plants, x, y, ground(x, y), rng.uniform(0.4, 0.65), rng.choice(FLOWERS), rng)
    for x, y in scatter(rng, 25, 40, keep=lambda x, y: x * x + y * y > 64):
        add_bush(plants, x, y, ground(x, y), rng.uniform(0.5, 0.9), (0.15, 0.5, 0.1), rng)
    for x, y in scatter(rng, 7, 40, keep=lambda x, y: x * x + y * y > 100, spacing=8):
        add_broadleaf(plants, x, y, ground(x, y), rng.uniform(1.0, 1.5), rng)
    plants = plants.build("Plants", material)

    gusts = add_mover("Gusts", (0.25, 0, 0))
    flutter = add_mover("Flutter", (0.4, 0.3, 0))
    add_wind(plants, gusts, flutter, strength=0.6)

    add_orbit_camera(target=(0, 0, 0.8), distance=22, height=4, start=0, sweep=40)
