import math
import random

import bpy
from mathutils import Vector

from modules.nature import (FPS, Shader, MeshBuilder, setup_stage, overcast, add_glare, add_blade, add_mover, add_wind,
                            add_displace, add_camera, add_rain, keyframes, blade_material)

# Strikes: (second, where the bolt meets the ground, how long it flickers in frames).
STRIKES = [(1.5, (-30.0, 140.0), 7), (4.6, (25.0, 95.0), 9), (7.8, (-8.0, 170.0), 8)]
# Sheet lightning: flashes hidden inside the cloud.
SHEETS = [(3.2, (40.0, 200.0)), (6.3, (-60.0, 180.0)), (9.2, (10.0, 220.0))]
CLOUD_BASE = 32.0


def cloud_material(drift):
    # Heavy, churning cloud: billowing noise that is dense at the base and
    # thins out above, carried along by the wind (the drift empty).
    shader = Shader("StormCloud")
    nodes = shader.tree.nodes
    nodes.remove(shader.bsdf)
    coords = shader.node("ShaderNodeTexCoord", object=drift).outputs["Object"]
    stretched = shader.node("ShaderNodeMapping", {"Vector": coords, "Scale": (0.015, 0.022, 0.06)}).outputs[0]
    billows = shader.noise(stretched, 1.0, detail=8.0, roughness=0.6, distortion=0.3).outputs["Fac"]
    height = shader.node("ShaderNodeSeparateXYZ", {0: shader.node("ShaderNodeTexCoord").outputs["Generated"]}).outputs[2]
    falloff = shader.node("ShaderNodeMapRange", {"Value": height, 1: 1.0, 2: 0.2}).outputs[0]
    density = shader.math('MULTIPLY', shader.math('MAXIMUM', shader.math('SUBTRACT', billows, 0.45), 0.0), 6.0)
    density = shader.math('MULTIPLY', density, falloff)
    # A faint glow with the density stands in for light scattered inside the
    # cloud, so its billows read even between flashes.
    glow = shader.math('MULTIPLY', billows, shader.math('MULTIPLY', falloff, 0.05))
    volume = shader.node("ShaderNodeVolumePrincipled", {"Color": (0.32, 0.34, 0.38), "Density": density, "Anisotropy": 0.2,
                                                        "Emission Color": (0.5, 0.55, 0.65), "Emission Strength": glow})
    shader.tree.links.new(volume.outputs[0], shader.output.inputs["Volume"])
    return shader.material


def add_clouds():
    drift = add_mover("CloudDrift", (-0.25, 0.0, 0.0))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 150, CLOUD_BASE + 12))
    clouds = bpy.context.active_object
    clouds.name = "Clouds"
    clouds.scale = (500, 320, 24)
    clouds.data.materials.append(cloud_material(drift))
    eevee = bpy.context.scene.eevee
    eevee.volumetric_end = 450
    eevee.volumetric_tile_size = '8'
    eevee.volumetric_samples = 32
    return clouds


def bolt_path(rng, start, end, roughness, depth):
    # Midpoint displacement: split each segment and nudge the middle sideways.
    points = [start, end]
    for _ in range(depth):
        refined = [points[0]]
        for a, b in zip(points, points[1:]):
            middle = (a + b) / 2
            span = (b - a).length
            middle += Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 0.3))) * (roughness * span)
            refined += [middle, b]
        points = refined
    return points


def add_strand(builder, points, radius):
    # A thin tube along points, tapering to the end.
    sides = 5
    verts, faces = [], []
    for k, point in enumerate(points):
        direction = (points[min(k + 1, len(points) - 1)] - points[max(k - 1, 0)]).normalized()
        side = direction.cross(Vector((1, 0, 0))).normalized()
        other = direction.cross(side)
        r = radius * (1 - 0.6 * k / len(points))
        for i in range(sides):
            a = 2 * math.pi * i / sides
            verts.append(tuple(point + (side * math.cos(a) + other * math.sin(a)) * r))
    for k in range(len(points) - 1):
        for i in range(sides):
            j = (i + 1) % sides
            faces.append([k * sides + i, k * sides + j, (k + 1) * sides + j, (k + 1) * sides + i])
    builder.add(verts, faces)


def bolt_material(index):
    shader = Shader(f"Lightning.{index}")
    shader.tree.nodes.remove(shader.bsdf)
    glow = shader.node("ShaderNodeEmission", {"Color": (0.75, 0.82, 1.0), "Strength": 60.0})
    shader.tree.links.new(glow.outputs[0], shader.output.inputs["Surface"])
    return shader.material, glow.inputs["Strength"]


def flicker(frames):
    # A return stroke and its re-strikes: (frame offset, brightness 0..1).
    pattern = [(0, 1.0), (1, 0.35), (2, 0.9), (3, 0.0), (4, 0.6), (5, 0.15), (6, 0.8), (7, 0.0), (9, 0.4), (10, 0.0)]
    return [(f, b) for f, b in pattern if f < frames] + [(frames, 0.0)]


def add_bolt(rng, index, ground, frames):
    # A forked bolt from the cloud base to the ground, with branches.
    start = Vector((ground[0] + rng.uniform(-15, 15), ground[1] + rng.uniform(-10, 10), CLOUD_BASE + 2))
    trunk = bolt_path(rng, start, Vector((ground[0], ground[1], 0.0)), 0.18, 7)
    builder = MeshBuilder()
    add_strand(builder, trunk, 0.18)
    for _ in range(9):
        k = rng.randrange(4, len(trunk) // 2)
        origin = trunk[k]
        reach = rng.uniform(4, 12)
        tip = origin + Vector((rng.uniform(-1, 1) * reach, rng.uniform(-1, 1) * reach * 0.5, -rng.uniform(0.6, 1.2) * reach))
        add_strand(builder, bolt_path(rng, origin, tip, 0.22, 5), 0.07)
    material, strength = bolt_material(index)
    return builder.build(f"Lightning.{index}", [material], smooth=False), strength, start


def add_flash(index, location, start_frame, pattern, energy, bolt=None, strength=None, world=None):
    # The light of one strike: a big point light (and the bolt itself, and
    # the sky) following the flicker pattern.
    light_data = bpy.data.lights.new(name=f"Flash.{index}", type='POINT')
    light_data.color = (0.8, 0.85, 1.0)
    light_data.shadow_soft_size = 5.0
    light = bpy.data.objects.new(name=f"Flash.{index}", object_data=light_data)
    bpy.context.collection.objects.link(light)
    light.location = location
    keys = [(start_frame - 1, 0.0)] + [(start_frame + f, b) for f, b in pattern]
    for frame, brightness in keys:
        light_data.energy = energy * brightness
        light_data.keyframe_insert("energy", frame=frame)
        if bolt:
            bolt.hide_render = brightness == 0.0
            bolt.keyframe_insert("hide_render", frame=frame)
            strength.default_value = 80.0 * brightness
            strength.keyframe_insert("default_value", frame=frame)
        if world:
            world.default_value = 0.6 + 0.8 * brightness * (1.0 if bolt else 0.5)
            world.keyframe_insert("default_value", frame=frame)
    hold_keys(light_data, *([bolt.active_material.node_tree] if bolt else []), *([world.id_data] if world else []))


def hold_keys(*owners):
    # Lightning snaps on and off: no easing between keyframes.
    for owner in owners:
        for layer in owner.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for point in curve.keyframe_points:
                            point.interpolation = 'CONSTANT'


def add_field(rng, gusts, flutter):
    # Long meadow grass from the camera out towards the storm, whipped by the wind.
    builder = MeshBuilder(attributes=("height", "tint"), groups=("wind",))
    placed = 0
    while placed < 70000:
        d = rng.uniform(1.0, 120.0)
        if rng.random() > 1 / (1 + (d / 8) ** 1.5):
            continue
        x = rng.uniform(-1, 1) * (2 + 0.75 * d)
        grow = 1 + 0.04 * d
        height = rng.uniform(0.25, 0.6) * grow
        add_blade(builder, rng, x, d, height, height * 0.035, segments=4 if d < 10 else 2, tint=rng.random(),
                  crease=d < 10, reach=0.6 * grow)
        placed += 1
    grass = builder.build("Grass", [blade_material()])
    add_wind(grass, gusts, flutter, size=3.0, strength=0.35)
    return grass


def tree_material():
    shader = Shader("Conifers")
    noise = shader.noise(shader.coords("Object"), 3.0, detail=4.0).outputs["Fac"]
    color = shader.ramp(noise, [(0.3, (0.005, 0.012, 0.006)), (0.7, (0.015, 0.03, 0.012))])
    return shader.surface(color, 0.8)


def add_treeline(rng, gusts):
    # A dark band of conifers along the horizon, swaying.
    builder = MeshBuilder(groups=("wind",))
    for _ in range(700):
        x, y = rng.uniform(-260, 260), rng.uniform(230, 280)
        height = rng.uniform(12, 24)
        sides = 7
        # Three tiers of drooping branches.
        for tier in range(3):
            bottom = height * (0.15 + 0.25 * tier)
            radius = 0.3 * height * (1 - 0.28 * tier)
            ring = [(x + radius * math.cos(2 * math.pi * i / sides + tier), y + radius * math.sin(2 * math.pi * i / sides + tier),
                     bottom - (0.06 * height if i % 2 else 0.0)) for i in range(sides)]
            top = bottom + height * (0.45 - 0.05 * tier)
            builder.add(ring + [(x, y, top)], [[i, (i + 1) % sides, sides] for i in range(sides)],
                        wind=[bottom / height] * sides + [top / height])
    trees = builder.build("Treeline", [tree_material()], smooth=False)
    add_displace(trees, gusts, size=20.0, strength=1.5, direction='X', mid_level=0.3)
    return trees


def ground_material():
    shader = Shader("Ground")
    noise = shader.noise(shader.coords("Object"), 0.3, detail=6.0).outputs["Fac"]
    color = shader.ramp(noise, [(0.35, (0.01, 0.015, 0.006)), (0.65, (0.03, 0.04, 0.015))])
    return shader.surface(color, 0.6)


def basicthunderstorm():
    setup_stage(sun_elevation=25, sun_rotation=200, sun_energy=0.8, sky_strength=0.0)
    overcast(color=(0.07, 0.08, 0.095), strength=0.6)
    world = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]
    rng = random.Random(13)
    bpy.ops.mesh.primitive_plane_add(size=1200, location=(0, 300, 0))
    bpy.context.active_object.data.materials.append(ground_material())
    gusts = add_mover("Gusts", (0.4, 0.0, 0.0))
    flutter = add_mover("Flutter", (0.15, 0.0, 0.12))
    add_field(rng, gusts, flutter)
    add_treeline(rng, gusts)
    add_clouds()
    for index, (second, ground, frames) in enumerate(STRIKES):
        bolt, strength, top = add_bolt(rng, index, ground, frames)
        start = int(second * FPS)
        add_flash(index, top - Vector((0, 0, 6)), start, flicker(frames), 1.2e6, bolt, strength, world)
    for index, (second, spot) in enumerate(SHEETS):
        add_flash(len(STRIKES) + index, (spot[0], spot[1], CLOUD_BASE + 10), int(second * FPS), flicker(6), 2e6, world=world)
    add_rain(((-30.0, 30.0), (3.0, 70.0)), height=25.0, count=35000, speed=9.0, wind=(4.0, 1.0), length=0.9, width=0.01,
             brightness=0.2, opacity=0.25)
    add_glare(0.8)
    _, focus = add_camera((0.0, 0.0, 1.6), (-5.0, 100.0, 14.0), lens=24)
    keyframes(focus, "location", {1: (-8.0, 100.0, 14.0), bpy.context.scene.frame_end: (8.0, 100.0, 16.0)})
