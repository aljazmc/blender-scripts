import math
import random

import bpy

from modules.landscape import (
    MeshBuilder,
    add_broadleaf,
    add_conifer,
    add_displace,
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

WATER = -0.6
GRASS = ((0.3, 0.75, 0.1), (0.45, 0.8, 0.1), (0.2, 0.6, 0.12))
FLOWERS = ((1.0, 0.15, 0.1), (1.0, 0.85, 0.1), (0.3, 0.4, 1.0))


def river_center(x):
    return 5 * math.sin(x / 10)


def river_distance(x, y):
    return abs(y - river_center(x))


def ground(x, y):
    # Rolling hills flatten towards the river, which cuts a channel below the water line.
    d = river_distance(x, y)
    return (0.6 + hills(x, y, 2.0)) * smoothstep(4, 14, d) - 2.0 * (1 - smoothstep(2.5, 7, d))


def ground_color(z, slope):
    if z < WATER + 0.35:
        return (0.75, 0.65, 0.4)
    if slope > 0.45:
        return (0.5, 0.48, 0.45)
    f = smoothstep(-0.5, 2.0, z)
    return (0.2 + 0.2 * f, 0.55 + 0.15 * f, 0.1)


def add_water_material(flow):
    # Teal water with white foam streaks that drift along with the flow.
    material = bpy.data.materials.new(name="Water")
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.08
    coords = nodes.new(type="ShaderNodeTexCoord")
    coords.object = flow
    foam = nodes.new(type="ShaderNodeTexNoise")
    foam.inputs["Scale"].default_value = 1.2
    foam.inputs["Detail"].default_value = 4.0
    links.new(coords.outputs["Object"], foam.inputs["Vector"])
    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.55
    ramp.color_ramp.elements[0].color = (0.0, 0.3, 0.45, 1.0)
    ramp.color_ramp.elements[1].position = 0.68
    ramp.color_ramp.elements[1].color = (0.9, 0.95, 1.0, 1.0)
    links.new(foam.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return material


def add_river(flow, ripples, length=100, width=14, step=1.25):
    # A strip of triangles along the river at the water line; waves roll
    # downstream with the flow and wind ripples run across them.
    columns, rows = int(length / step), int(width / step)
    verts = []
    for i in range(columns + 1):
        x = -length / 2 + i * step
        verts += [(x, river_center(x) - width / 2 + j * step, WATER) for j in range(rows + 1)]
    faces = []
    for i in range(columns):
        for j in range(rows):
            a, b = i * (rows + 1) + j, (i + 1) * (rows + 1) + j
            faces += [[a, b, b + 1], [a, b + 1, a + 1]] if (i + j) % 2 else [[a, b, a + 1], [b, b + 1, a + 1]]
    mesh = bpy.data.meshes.new(name="River")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(add_water_material(flow))
    river = bpy.data.objects.new(name="River", object_data=mesh)
    bpy.context.collection.objects.link(river)
    add_displace(river, flow, size=2.0, strength=0.5, direction='Z', mid_level=0.5, group=None)
    add_displace(river, ripples, size=0.6, strength=0.15, direction='Z', mid_level=0.5, group=None)
    return river


def basicriverscape():
    setup_stage()
    rng = random.Random(3)
    material = add_flat_material()

    land = MeshBuilder(rng)
    add_terrain(land, size=100, cells=64, height=ground, color=ground_color)
    for x, y in scatter(rng, 40, 45, keep=lambda x, y: 3 < river_distance(x, y) < 8):
        add_rock(land, x, y, ground(x, y), rng.uniform(0.3, 0.9), rng)
    land.build("Terrain", material)

    plants = MeshBuilder(rng)
    # Trees stand back from the river, and off the camera's path (y < 0, around 26 m out).
    def tree_spot(x, y):
        return river_distance(x, y) > 9 and (y > -5 or x * x + y * y > 34 ** 2)

    for x, y in scatter(rng, 45, 48, keep=tree_spot, spacing=3):
        if rng.random() < 0.7:
            add_broadleaf(plants, x, y, ground(x, y), rng.uniform(0.9, 1.4), rng)
        else:
            add_conifer(plants, x, y, ground(x, y), rng.uniform(0.9, 1.3), rng)
    for x, y in scatter(rng, 7000, 45, keep=lambda x, y: river_distance(x, y) > 6):
        add_tuft(plants, x, y, ground(x, y), rng.uniform(0.35, 0.65), rng.choice(GRASS), rng)
    # Reeds along the water's edge.
    for x, y in scatter(rng, 500, 45, keep=lambda x, y: 4.5 < river_distance(x, y) < 6.5):
        add_tuft(plants, x, y, ground(x, y), rng.uniform(0.9, 1.4), (0.25, 0.45, 0.1), rng, blades=4, lean=0.1)
    for x, y in scatter(rng, 300, 40, keep=lambda x, y: river_distance(x, y) > 7):
        add_flower(plants, x, y, ground(x, y), rng.uniform(0.4, 0.6), rng.choice(FLOWERS), rng)
    plants = plants.build("Plants", material)

    gusts = add_mover("Gusts", (0.25, 0, 0))
    flutter = add_mover("Flutter", (0.4, 0.3, 0))
    add_wind(plants, gusts, flutter, strength=0.6)
    add_river(flow=add_mover("Flow", (0.12, 0, 0)), ripples=add_mover("Ripples", (0.3, 0.1, 0)))

    add_orbit_camera(target=(0, 0, -0.5), distance=26, height=13, start=-20, sweep=50)
