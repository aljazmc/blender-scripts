import math
import random

import bpy

from modules.nature import (Shader, MeshBuilder, setup_stage, add_blade, add_leaf, add_mover, add_wind,
                            add_camera, keyframes)

CAMERA_Y = -1.4


def blade_material():
    # Dark at the root, fresh green up the blade with veins along it, a few
    # dry straw-coloured blades and browned tips; thin enough to glow when backlit.
    shader = Shader("GrassBlade")
    height = shader.attribute("height")
    tint = shader.attribute("tint")
    u, v = shader.uv()
    green = shader.ramp(height, [(0.0, (0.02, 0.05, 0.01)), (0.35, (0.06, 0.18, 0.025)), (1.0, (0.2, 0.36, 0.05))])
    green = shader.mix(1.0, green, shader.ramp(tint, [(0.0, (0.7, 0.95, 0.65)), (0.6, (1.0, 1.0, 1.0)), (0.9, (1.0, 0.85, 0.5))]), 'MULTIPLY')
    straw = shader.ramp(height, [(0.0, (0.12, 0.09, 0.04)), (1.0, (0.55, 0.45, 0.22))])
    dry = shader.math('GREATER_THAN', tint, 0.93)
    color = shader.mix(dry, green, straw)
    tip = shader.math('MULTIPLY', shader.math('GREATER_THAN', height, 0.9), shader.math('GREATER_THAN', tint, 0.7))
    color = shader.mix(shader.math('MULTIPLY', tip, 0.6), color, (0.3, 0.22, 0.08))
    veins_at = shader.node("ShaderNodeCombineXYZ", {0: shader.math('MULTIPLY', u, 14.0), 1: shader.math('MULTIPLY', v, 0.8), 2: shader.math('MULTIPLY', tint, 40.0)})
    veins = shader.noise(veins_at.outputs[0], 3.0, detail=2.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(veins, [(0.3, (0.75, 0.75, 0.75)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    normal = shader.bump(veins, 0.15)
    return shader.surface(color, 0.42, normal, translucency=0.4, Specular_IOR_Level=0.6)


def seed_material():
    shader = Shader("SeedHead")
    noise = shader.noise(shader.coords("Object"), 300.0).outputs["Fac"]
    color = shader.ramp(noise, [(0.35, (0.28, 0.2, 0.12)), (0.65, (0.5, 0.42, 0.25))])
    return shader.surface(color, 0.6, translucency=0.25)


def soil_material():
    # Dark earth with lighter grit, dead thatch and clods in the bump.
    shader = Shader("Soil")
    coords = shader.coords("Object")
    patches = shader.noise(coords, 3.0, detail=6.0, roughness=0.6).outputs["Fac"]
    color = shader.ramp(patches, [(0.35, (0.05, 0.035, 0.02)), (0.6, (0.11, 0.08, 0.05))])
    thatch = shader.noise(shader.coords("Object", (1.0, 8.0, 1.0)), 30.0, detail=3.0, distortion=2.0).outputs["Fac"]
    color = shader.mix(shader.math('GREATER_THAN', thatch, 0.62), color, (0.3, 0.24, 0.12))
    grit = shader.voronoi(coords, 180.0)
    color = shader.mix(shader.math('LESS_THAN', grit.outputs["Distance"], 0.12), color, (0.22, 0.2, 0.17))
    clods = shader.noise(coords, 40.0, detail=8.0, roughness=0.7).outputs["Fac"]
    normal = shader.bump(shader.math('ADD', clods, shader.math('MULTIPLY', grit.outputs["Distance"], 0.5)), 0.6)
    return shader.surface(color, 0.95, normal)


def field_spots(rng, count):
    # Spots spread over the ground the camera sees, densest close up.
    def width(d):
        return 0.4 + 0.7 * d

    def density(d):
        return 1 / (1 + (d / 1.2) ** 2)

    near, far = 0.2, 25.0
    peak = max(width(near + i * 0.05) * density(near + i * 0.05) for i in range(500))
    spots = []
    while len(spots) < count:
        d = rng.uniform(near, far)
        if rng.random() * peak < width(d) * density(d):
            spots.append((rng.uniform(-width(d), width(d)), CAMERA_Y + d, d))
    return spots


def add_field(rng, blades, stems):
    builder = MeshBuilder(attributes=("height", "tint"), groups=("wind",))
    for x, y, d in field_spots(rng, blades):
        grow = 1 + 0.06 * d
        height = rng.uniform(0.15, 0.4) * grow
        segments = 4 if d < 3 else 3 if d < 8 else 2
        add_blade(builder, rng, x, y, height, rng.uniform(0.005, 0.009) * grow, segments=segments,
                  tint=rng.random(), crease=d < 8, reach=0.8)
    for x, y, d in field_spots(rng, stems):
        if not 1.3 < d < 6:
            continue
        add_stem(builder, rng, x, y, rng.uniform(0.5, 0.85))
    return builder.build("Grass", [blade_material(), seed_material()])


def add_stem(builder, rng, x, y, height):
    # A tall stalk with a nodding seed head of spikelets.
    add_blade(builder, rng, x, y, height, 0.003, segments=6, lean=0.25, tint=0.75, reach=0.8)
    stalk = builder.verts[-1]
    for k in range(14):
        t = k / 14
        z = stalk[2] - 0.12 * t
        angle = k * 2.4
        reach = (0.8 - 0.4 * t) * 0.03
        forward = (math.cos(angle) * 0.5, math.sin(angle) * 0.5, 1.0)
        tip_wind = min(z / 0.8, 1.0) ** 1.4
        add_leaf(builder, (stalk[0], stalk[1], z), forward, (math.cos(angle + 1.5), math.sin(angle + 1.5), 0.0),
                 reach + 0.006, 0.004, material=1, rows=3, height=1.0, tint=0.5, wind=tip_wind)


def add_ground():
    bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(soil_material())
    return ground


def basicgrass():
    setup_stage(sun_elevation=14, sun_rotation=150, sun_energy=6.0, sky_strength=0.25)
    rng = random.Random(7)
    add_ground()
    grass = add_field(rng, blades=45000, stems=400)
    gusts = add_mover("Gusts", (0.1, 0.0, 0.0))
    flutter = add_mover("Flutter", (0.04, 0.0, 0.03))
    add_wind(grass, gusts, flutter, size=1.5, strength=0.3)
    camera, focus = add_camera((0.25, CAMERA_Y, 0.6), (0.0, 0.3, 0.15), lens=40, fstop=4.0)
    end = bpy.context.scene.frame_end
    keyframes(camera, "location", {1: (0.25, CAMERA_Y, 0.6), end: (-0.2, CAMERA_Y + 0.35, 0.55)})
    keyframes(focus, "location", {1: (0.0, 0.3, 0.15), end: (-0.1, 0.5, 0.18)})
