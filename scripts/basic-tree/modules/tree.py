import math
import random

import bpy
from mathutils import Vector

from modules.nature import (Shader, MeshBuilder, setup_stage, add_blade, add_leaf, add_mover, add_displace,
                            add_wind, add_camera)

REACH = 9.0  # path length from the roots to the outermost twigs, roughly
UP = Vector((0, 0, 1))
CROWN_CENTRE = Vector((0, 0, 6.3))
CROWN_RADII = Vector((5.0, 5.0, 3.8))

# Per level: length, base radius, sides, children, branching angle, upward pull.
LEVELS = [
    (5.0, 0.3, 16, 10, 0.0, 0.0),
    (5.0, 0.13, 10, 9, math.radians(52), 0.04),
    (2.0, 0.045, 6, 9, math.radians(50), 0.0),
    (0.6, 0.012, 4, 0, math.radians(40), -0.02),
]


def bark_material():
    # Long fissured plates (stretched along the branch in UV space), dark in
    # the cracks, with moss on the upward-facing side.
    shader = Shader("Bark")
    u, v = shader.uv()
    at = shader.node("ShaderNodeCombineXYZ", {0: shader.math('MULTIPLY', u, 7.0), 1: shader.math('MULTIPLY', v, 1.8)}).outputs[0]
    wobble = shader.noise(at, 2.0, detail=3.0).outputs["Color"]
    at = shader.node("ShaderNodeMix", {0: 0.25, 4: at, 5: wobble}, data_type='VECTOR').outputs[1]
    plates = shader.voronoi(at, 4.0, 'DISTANCE_TO_EDGE').outputs["Distance"]
    ridges = shader.node("ShaderNodeMapRange", {"Value": plates, 1: 0.0, 2: 0.12}).outputs[0]
    grain = shader.noise(at, 25.0, detail=6.0, roughness=0.65).outputs["Fac"]
    color = shader.ramp(ridges, [(0.0, (0.012, 0.01, 0.008)), (0.6, (0.07, 0.055, 0.045)), (1.0, (0.13, 0.11, 0.09))])
    color = shader.mix(1.0, color, shader.ramp(grain, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.15, 1.1, 1.05))]), 'MULTIPLY')
    normal_z = shader.node("ShaderNodeSeparateXYZ", {0: shader.node("ShaderNodeNewGeometry").outputs["Normal"]}).outputs[2]
    moss_noise = shader.noise(shader.coords("Object"), 3.0, detail=5.0).outputs["Fac"]
    moss = shader.math('MULTIPLY', shader.node("ShaderNodeMapRange", {"Value": normal_z, 1: 0.1, 2: 0.7}).outputs[0],
                       shader.node("ShaderNodeMapRange", {"Value": moss_noise, 1: 0.45, 2: 0.6}).outputs[0])
    color = shader.mix(shader.math('MULTIPLY', moss, ridges), color, (0.07, 0.11, 0.025))
    height = shader.math('ADD', ridges, shader.math('MULTIPLY', grain, 0.3))
    return shader.surface(color, 0.85, shader.bump(height, 0.8, 0.03))


def leaf_material():
    # Varied greens with a pale midrib and side veins, paler underneath and
    # glowing where the sun shines through.
    shader = Shader("Leaf")
    tint = shader.attribute("tint")
    u, v = shader.uv()
    color = shader.ramp(tint, [(0.0, (0.045, 0.085, 0.006)), (0.5, (0.1, 0.16, 0.01)), (0.9, (0.2, 0.26, 0.02)),
                               (0.97, (0.42, 0.34, 0.05))])
    across = shader.math('ABSOLUTE', shader.math('SUBTRACT', u, 0.5))
    midrib = shader.math('LESS_THAN', across, 0.035)
    sides = shader.math('SINE', shader.math('MULTIPLY', shader.math('SUBTRACT', v, shader.math('MULTIPLY', across, 1.3)), 55.0))
    veins = shader.math('MAXIMUM', midrib, shader.math('MULTIPLY', shader.math('GREATER_THAN', sides, 0.93), 0.6))
    color = shader.mix(shader.math('MULTIPLY', veins, 0.5), color, (0.35, 0.42, 0.12))
    backfacing = shader.node("ShaderNodeNewGeometry").outputs["Backfacing"]
    color = shader.mix(shader.math('MULTIPLY', backfacing, 0.5), color, (0.25, 0.32, 0.12))
    blotches = shader.noise(shader.coords("Object"), 60.0, detail=3.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(blotches, [(0.3, (0.8, 0.8, 0.8)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    normal = shader.bump(veins, -0.3, 0.002)
    return shader.surface(color, 0.45, normal, translucency=0.35, Specular_IOR_Level=0.6)


def lawn_material():
    shader = Shader("Lawn")
    coords = shader.coords("Object")
    patches = shader.noise(coords, 0.6, detail=6.0, roughness=0.6).outputs["Fac"]
    color = shader.ramp(patches, [(0.35, (0.03, 0.05, 0.006)), (0.55, (0.065, 0.09, 0.012)), (0.7, (0.12, 0.11, 0.035))])
    fine = shader.noise(coords, 120.0, detail=4.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(fine, [(0.3, (0.6, 0.6, 0.6)), (0.7, (1.2, 1.2, 1.2))]), 'MULTIPLY')
    return shader.surface(color, 0.9, shader.bump(fine, 0.4))


def blade_material():
    shader = Shader("GrassBlade")
    height = shader.attribute("height")
    tint = shader.attribute("tint")
    color = shader.ramp(height, [(0.0, (0.025, 0.05, 0.006)), (1.0, (0.15, 0.24, 0.025))])
    color = shader.mix(1.0, color, shader.ramp(tint, [(0.0, (0.7, 0.9, 0.6)), (1.0, (1.1, 1.0, 0.7))]), 'MULTIPLY')
    return shader.surface(color, 0.5, translucency=0.3)


def frame_for(direction):
    # Two unit vectors perpendicular to direction.
    side = direction.cross(UP if abs(direction.z) < 0.95 else Vector((1, 0, 0))).normalized()
    return side, direction.cross(side).normalized()


def add_tube(builder, points, radii, sides, path, flare=False):
    # A tapered tube along points. UVs are in metres (around, along) so the bark
    # keeps its scale; the "wind" weight grows with path length from the roots.
    verts, faces, uvs, weights = [], [], [], []
    circumference = 2 * math.pi * radii[0]
    side, other = frame_for((points[1] - points[0]).normalized())
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    for k, point in enumerate(points):
        direction = (points[min(k + 1, len(points) - 1)] - points[max(k - 1, 0)]).normalized()
        # Carry the frame along the curve so the tube doesn't twist.
        side = (side - direction * side.dot(direction)).normalized()
        other = direction.cross(side)
        for i in range(sides):
            angle = 2 * math.pi * i / sides
            radius = radii[k]
            if flare:
                # Buttress roots spreading the base of the trunk.
                radius *= 1 + math.exp(-point.z / 0.3) * (0.45 + 0.25 * math.sin(5 * angle + 0.7))
            verts.append(tuple(point + (side * math.cos(angle) + other * math.sin(angle)) * radius))
            weights.append(min((path + lengths[k]) / REACH, 1.0) ** 1.6)
    for k in range(len(points) - 1):
        for i in range(sides):
            j = (i + 1) % sides
            faces.append([k * sides + i, k * sides + j, (k + 1) * sides + j, (k + 1) * sides + i])
            u0, u1 = circumference * i / sides, circumference * (i + 1) / sides
            uvs.append([(u0, lengths[k]), (u1, lengths[k]), (u1, lengths[k + 1]), (u0, lengths[k + 1])])
    builder.add(verts, faces, uvs, material=0, wind=weights)


def crown_room(start, direction):
    # How far from start along direction until the crown's ellipsoid is left.
    p = Vector(x / r for x, r in zip(start - CROWN_CENTRE, CROWN_RADII))
    d = Vector(x / r for x, r in zip(direction, CROWN_RADII))
    a, b, c = d.dot(d), 2 * p.dot(d), p.dot(p) - 1
    return max((-b + math.sqrt(max(b * b - 4 * a * c, 0.0))) / (2 * a), 0.0)


def grow(builder, rng, start, direction, level, scale, path):
    # One branch and, recursively, its side branches and leaves; branches are
    # cut short where they would poke out of the crown.
    length, radius, sides, children, _, pull = LEVELS[level]
    length *= scale
    if level:
        length = max(min(length, crown_room(start, direction)), 0.4 * length)
    radius *= scale ** 1.5
    segments = max(3, int(length / 0.2))
    points, step = [start], length / segments
    for _ in range(segments):
        wander = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))) * (0.12 if level else 0.03)
        direction = (direction + wander + UP * pull).normalized()
        points.append(points[-1] + direction * step)
    tip = 0.25 if level < 3 else 0.4
    radii = [radius * (1 - (1 - tip) * (k / segments) ** 0.8) for k in range(segments + 1)]
    add_tube(builder, points, radii, sides, path, flare=level == 0)
    if level + 1 < len(LEVELS):
        child_angle = LEVELS[level + 1][4]
        first = 0.5 if level == 0 else 0.2
        spin = rng.uniform(0, 2 * math.pi)
        for c in range(children):
            t = first + (1 - first) * (c + rng.uniform(0.2, 0.8)) / children
            k = min(int(t * segments), segments - 1)
            here = points[k].lerp(points[k + 1], t * segments - k)
            heading = (points[k + 1] - points[k]).normalized()
            side, other = frame_for(heading)
            spin += math.radians(137.5)
            out = (side * math.cos(spin) + other * math.sin(spin))
            angle = child_angle * rng.uniform(0.8, 1.2)
            child = (heading * math.cos(angle) + out * math.sin(angle)).normalized()
            child_scale = scale * (1.0 - 0.45 * t if level else 1.1 - 0.4 * t) * rng.uniform(0.85, 1.1)
            grow(builder, rng, here, child, level + 1, child_scale, path + t * length)
        if level == 0:
            # The leader carries on from the top of the trunk.
            grow(builder, rng, points[-1], direction, 1, 0.9, path + length)
    if level >= 2:
        add_leaves(builder, rng, points, path, length, 55 if level == 3 else 16)


def add_leaves(builder, rng, points, path, length, count):
    for _ in range(count):
        t = rng.uniform(0.15, 1.0)
        k = min(int(t * (len(points) - 1)), len(points) - 2)
        base = points[k].lerp(points[k + 1], t * (len(points) - 1) - k)
        heading = (points[k + 1] - points[k]).normalized()
        side, other = frame_for(heading)
        spin = rng.uniform(0, 2 * math.pi)
        out = side * math.cos(spin) + other * math.sin(spin)
        forward = (heading * 0.6 + out + Vector((0, 0, -0.2))).normalized()
        normal = (UP + out * 0.6 + Vector((rng.gauss(0, 0.3), rng.gauss(0, 0.3), 0))).normalized()
        size = rng.uniform(0.75, 1.15)
        stem = base + forward * 0.03
        wind = min((path + t * length) / REACH, 1.0) ** 1.6
        rows = 5
        flutter = [r / rows for r in range(rows) for _ in range(3)] + [1.0]
        add_leaf(builder, stem, forward, normal, 0.16 * size, 0.095 * size, material=1, rows=rows,
                 tint=rng.random(), wind=wind, flutter=flutter)


def add_tree(rng):
    builder = MeshBuilder(attributes=("tint",), groups=("wind", "flutter"))
    grow(builder, rng, Vector((0, 0, -0.2)), UP, 0, 1.0, 0.0)
    # A few surface roots snaking away from the trunk.
    for r in range(6):
        angle = r * 2 * math.pi / 6 + rng.uniform(-0.3, 0.3)
        out = Vector((math.cos(angle), math.sin(angle), 0))
        points = [out * 0.25 + Vector((0, 0, 0.05))]
        for k in range(8):
            points.append(points[-1] + (out + Vector((rng.gauss(0, 0.3), rng.gauss(0, 0.3), -0.12 - 0.05 * k))) * 0.22)
        add_tube(builder, points, [0.08 * (1 - k / 9) ** 1.5 + 0.01 for k in range(9)], 8, 0.0)
    return builder.build("Tree", [bark_material(), leaf_material()])


def add_lawn(rng):
    bpy.ops.mesh.primitive_plane_add(size=200)
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(lawn_material())
    builder = MeshBuilder(attributes=("height", "tint"), groups=("wind",))
    for _ in range(40000):
        r = 16 * rng.random() ** 0.8
        angle = rng.uniform(0, 2 * math.pi)
        add_blade(builder, rng, r * math.cos(angle), r * math.sin(angle), rng.uniform(0.08, 0.22),
                  rng.uniform(0.006, 0.01), segments=3, tint=rng.random(), crease=False, reach=0.5)
    return builder.build("Grass", [blade_material()])


def basictree():
    setup_stage(sun_elevation=35, sun_rotation=60, sun_energy=5.0, sky_strength=0.2)
    rng = random.Random(3)
    tree = add_tree(rng)
    grass = add_lawn(rng)
    gusts = add_mover("Gusts", (0.12, 0.0, 0.0))
    sway = add_mover("Sway", (0.05, 0.0, 0.04))
    leaves = add_mover("Leaves", (0.3, 0.0, 0.2))
    add_displace(tree, gusts, size=6.0, strength=0.9, direction='X', mid_level=0.2)
    add_displace(tree, sway, size=3.0, strength=0.45, direction='Y')
    add_displace(tree, leaves, size=0.4, strength=0.05, direction='NORMAL', group="flutter")
    add_wind(grass, gusts, sway, size=2.0, strength=0.2)
    camera, _ = add_camera((0, -15, 2.0), (0, 0, 4.2), lens=30)
    pivot = bpy.data.objects.new(name="CameraPivot", object_data=None)
    bpy.context.collection.objects.link(pivot)
    camera.parent = pivot
    end = bpy.context.scene.frame_end
    pivot.driver_add("rotation_euler", 2).driver.expression = f"{math.radians(-20)} + frame / {end} * {math.radians(40)}"
