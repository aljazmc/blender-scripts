import math
import random

import bpy

from modules.nature import (FPS, Shader, MeshBuilder, setup_stage, overcast, clock, add_blade, add_leaf, add_mover, add_wind,
                            add_displace, add_camera, add_rain, keyframes, blade_material)


def ripples(shader, coords, seconds, scale, rate, offset):
    # Rings spreading from random points, each restarting at its own moment.
    at = shader.node("ShaderNodeVectorMath", {0: coords, 1: (offset, 2 * offset, 0.0)}, operation='ADD').outputs[0]
    cells = shader.voronoi(at, scale)
    chance = shader.node("ShaderNodeSeparateColor", {0: cells.outputs["Color"]}).outputs[0]
    phase = shader.math('FRACT', shader.math('ADD', shader.math('MULTIPLY', seconds, rate), shader.math('MULTIPLY', chance, 7.0)))
    distance = shader.math('ABSOLUTE', shader.math('SUBTRACT', cells.outputs["Distance"], shader.math('MULTIPLY', phase, 0.7)))
    ring = shader.math('MAXIMUM', shader.math('SUBTRACT', 1.0, shader.math('DIVIDE', distance, 0.05)), 0.0)
    fade = shader.math('POWER', shader.math('SUBTRACT', 1.0, phase), 2.0)
    return shader.math('MULTIPLY', shader.math('MULTIPLY', ring, ring), fade)


def street_material():
    # Rain-soaked cobbles: stones of varied colour set in dark joints, with
    # puddles gathering in the hollows; on the water, rings from the drops and
    # ruffles blown along by the wind.
    shader = Shader("Cobbles")
    coords = shader.coords("Object")
    seconds = clock(shader)
    stones = shader.voronoi(coords, 9.0, 'DISTANCE_TO_EDGE').outputs["Distance"]
    cells = shader.voronoi(coords, 9.0)
    tone = shader.node("ShaderNodeSeparateColor", {0: cells.outputs["Color"]}).outputs[0]
    color = shader.ramp(tone, [(0.0, (0.08, 0.075, 0.07)), (0.5, (0.16, 0.14, 0.12)), (1.0, (0.13, 0.13, 0.14))])
    grain = shader.noise(coords, 60.0, detail=6.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(grain, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    # Rounded stones: away from the cell edges and not too far from the centre.
    edges = shader.node("ShaderNodeMapRange", {"Value": stones, 1: 0.03, 2: 0.12}).outputs[0]
    middle = shader.node("ShaderNodeMapRange", {"Value": cells.outputs["Distance"], 1: 0.62, 2: 0.48}).outputs[0]
    joint = shader.math('MINIMUM', edges, middle)
    color = shader.mix(joint, (0.02, 0.018, 0.015), color)
    # Stones are domed, so water collects in the joints and the low patches.
    dome = shader.math('POWER', joint, 0.5)
    # Puddles in the low patches, the biggest just in front of the camera.
    low = shader.noise(coords, 0.9, detail=3.0).outputs["Fac"]
    spread = shader.node("ShaderNodeVectorMath", {0: coords, 1: (0.0, 0.4, 0.0)}, operation='DISTANCE').outputs["Value"]
    low = shader.math('ADD', low, shader.math('MULTIPLY', shader.math('MAXIMUM', shader.math('SUBTRACT', 0.9, spread), 0.0), 0.2))
    puddle = shader.node("ShaderNodeMapRange", {"Value": low, 1: 0.52, 2: 0.56}).outputs[0]
    water = shader.math('MAXIMUM', puddle, shader.math('MULTIPLY', shader.math('SUBTRACT', 1.0, joint), 0.8))
    rings = shader.math('ADD', ripples(shader, coords, seconds, 14.0, 1.3, 0.0), ripples(shader, coords, seconds, 11.0, 1.1, 3.7))
    breeze_at = shader.node("ShaderNodeMapping", {"Vector": coords, "Scale": (6.0, 14.0, 1.0)})
    breeze_at.inputs["Location"].driver_add("default_value", 0).driver.expression = f"-frame / {FPS} * 2.5"
    breeze = shader.noise(breeze_at.outputs[0], 4.0, detail=2.0).outputs["Fac"]
    surface = shader.math('ADD', shader.math('MULTIPLY', rings, 0.6), shader.math('MULTIPLY', breeze, 0.15))
    height = shader.math('ADD', shader.math('MULTIPLY', shader.math('ADD', dome, shader.math('MULTIPLY', grain, 0.2)),
                                            shader.math('SUBTRACT', 1.0, puddle)), shader.math('MULTIPLY', surface, water))
    color = shader.mix(puddle, shader.mix(1.0, color, (0.6, 0.6, 0.6), 'MULTIPLY'), (0.015, 0.016, 0.018))
    roughness = shader.math('ADD', 0.02, shader.math('MULTIPLY', shader.math('SUBTRACT', 1.0, water), 0.3))
    return shader.surface(color, roughness, shader.bump(height, 0.35, 0.004), Specular_IOR_Level=0.6)


def hedge_material():
    shader = Shader("Hedge")
    coords = shader.coords("Object")
    leaves = shader.voronoi(coords, 40.0)
    tone = shader.node("ShaderNodeSeparateColor", {0: leaves.outputs["Color"]}).outputs[1]
    color = shader.ramp(tone, [(0.0, (0.01, 0.03, 0.006)), (0.6, (0.04, 0.09, 0.015)), (1.0, (0.08, 0.13, 0.02))])
    return shader.surface(color, 0.3, shader.bump(leaves.outputs["Distance"], 0.8, 0.02), translucency=0.2)


def add_hedge(gusts):
    # A clipped hedge across the back, ragged at the edges, rustling.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 6.5, 0.8))
    hedge = bpy.context.active_object
    hedge.name = "Hedge"
    hedge.scale = (24, 1.2, 1.6)
    bpy.ops.object.transform_apply(scale=True)
    subdivide = hedge.modifiers.new(name="Subdivision", type='SUBSURF')
    subdivide.subdivision_type = 'SIMPLE'
    subdivide.levels = subdivide.render_levels = 6
    texture = bpy.data.textures.new(name="HedgeShape", type='CLOUDS')
    texture.noise_scale = 0.3
    ragged = hedge.modifiers.new(name="Ragged", type='DISPLACE')
    ragged.texture = texture
    ragged.strength = 0.25
    add_displace(hedge, gusts, size=1.5, strength=0.08, direction='X', group=None)
    hedge.data.materials.append(hedge_material())
    return hedge


def leaf_material():
    shader = Shader("WetLeaf")
    tint = shader.attribute("tint")
    color = shader.ramp(tint, [(0.0, (0.3, 0.07, 0.01)), (0.5, (0.45, 0.2, 0.02)), (1.0, (0.3, 0.25, 0.04))])
    return shader.surface(color, 0.15, translucency=0.2, Coat_Weight=0.8)


def add_floating_leaves(rng):
    # Fallen leaves drifting across the puddles with the wind, turning slowly.
    material = leaf_material()
    end = bpy.context.scene.frame_end
    for k in range(5):
        builder = MeshBuilder(attributes=("tint",))
        add_leaf(builder, (-0.03, 0, 0), (1, 0, 0), (0, 0, 1), 0.06, 0.035, tint=rng.random())
        leaf = builder.build(f"Leaf.{k}", [material])
        x, y = rng.uniform(-0.8, 0.1), rng.uniform(0.0, 1.5)
        speed, spin = rng.uniform(0.03, 0.06), rng.uniform(-0.4, 0.4)
        for frame in range(1, end + 1, 12):
            t = frame / FPS
            leaf.location = (x + speed * t + 0.01 * math.sin(2 * t + k), y + 0.01 * math.sin(1.3 * t + k), 0.002)
            leaf.rotation_euler = (0.04 * math.sin(3 * t + k), 0.04 * math.cos(2.5 * t), k + spin * t)
            leaf.keyframe_insert("location", frame=frame)
            leaf.keyframe_insert("rotation_euler", frame=frame)


def add_verges(rng, gusts, flutter):
    # Grass along both sides of the path, flattened and tossed by the gusts.
    builder = MeshBuilder(attributes=("height", "tint"), groups=("wind",))
    for _ in range(30000):
        side = rng.choice((-1, 1))
        x = side * (1.1 + abs(rng.gauss(0, 0.5)))
        y = rng.uniform(-1.5, 7.0)
        height = rng.uniform(0.1, 0.32)
        add_blade(builder, rng, x, y, height, height * 0.04, segments=4, tint=rng.random(), reach=0.35)
    grass = builder.build("Verge", [blade_material()])
    add_wind(grass, gusts, flutter, size=1.0, strength=0.12)
    return grass


def basicrain():
    setup_stage(sun_elevation=40, sun_rotation=-60, sun_energy=0.6, sky_strength=1.0)
    overcast()
    scene = bpy.context.scene
    # Screen-space reflections, so the hedge and verges show in the puddles.
    scene.eevee.use_raytracing = True
    scene.eevee.ray_tracing_options.resolution_scale = '2'
    rng = random.Random(4)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 3, 0))
    street = bpy.context.active_object
    street.name = "Street"
    street.data.materials.append(street_material())
    gusts = add_mover("Gusts", (0.1, 0.0, 0.0))
    flutter = add_mover("Flutter", (0.05, 0.0, 0.05))
    add_verges(rng, gusts, flutter)
    add_hedge(gusts)
    add_floating_leaves(rng)
    add_rain(((-2.5, 2.5), (-0.6, 5.0)), height=3.0, count=12000, speed=7.0, wind=(1.2, 0.3), length=0.12, width=0.0008,
             splash=0.006, brightness=0.5, opacity=0.25)
    camera, _ = add_camera((0.15, -1.0, 0.4), (0.0, 0.5, 0.0), lens=35, fstop=2.8)
    keyframes(camera, "location", {1: (0.15, -1.0, 0.4), scene.frame_end: (-0.15, -0.85, 0.36)})
