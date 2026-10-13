import math
import random

import bpy
from mathutils import Vector, noise

FPS = 24
DURATION = 10


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def set_timeline():
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FPS * DURATION


def smoothstep(edge0, edge1, x):
    x = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def hills(x, y, amplitude, scale=0.05):
    return amplitude * (noise.noise((x * scale, y * scale, 0.0)) + 0.3 * noise.noise((x * scale * 3, y * scale * 3, 5.0)))


def vary(color, amount, rng):
    return tuple(min(max(c + rng.uniform(-amount, amount), 0.0), 1.0) for c in color)


def setup_stage(sky=(0.35, 0.6, 1.0)):
    clear_scene()
    set_timeline()
    # AgX washes out saturated colours; Standard keeps them vivid.
    bpy.context.scene.view_settings.view_transform = 'Standard'
    background = bpy.context.scene.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (*sky, 1.0)
    background.inputs["Strength"].default_value = 0.6
    bpy.ops.object.light_add(type='SUN', rotation=(math.radians(55), 0, math.radians(-35)))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = 3.5
    sun.data.color = (1.0, 0.95, 0.85)
    sun.data.angle = math.radians(3)


def add_flat_material(name="LowPoly", roughness=0.8):
    # Base colour comes from the per-face "Color" attribute.
    material = bpy.data.materials.new(name=name)
    nodes = material.node_tree.nodes
    color = nodes.new(type="ShaderNodeVertexColor")
    color.layer_name = "Color"
    material.node_tree.links.new(color.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    nodes["Principled BSDF"].inputs["Roughness"].default_value = roughness
    return material


class MeshBuilder:
    # Collects low-poly pieces into one mesh: every face gets its own flat
    # colour and every vertex a "wind" weight, 0 at the roots and 1 at the tips.

    def __init__(self, rng):
        self.rng = rng
        self.verts, self.faces, self.colors, self.weights = [], [], [], []

    def add(self, verts, faces, color, jitter=0.04, base=0.0, height=None, power=1.5):
        offset = len(self.verts)
        self.verts += verts
        if height:
            self.weights += [min(max((v[2] - base) / height, 0.0), 1.0) ** power for v in verts]
        else:
            self.weights += [0.0] * len(verts)
        for face in faces:
            self.faces.append([offset + i for i in face])
            self.colors.append(vary(color, jitter, self.rng))

    def build(self, name, material):
        mesh = bpy.data.meshes.new(name=name)
        mesh.from_pydata(self.verts, [], self.faces)
        corners = []
        for face, color in zip(self.faces, self.colors):
            corners += [*color, 1.0] * len(face)
        mesh.color_attributes.new(name="Color", type='BYTE_COLOR', domain='CORNER').data.foreach_set("color", corners)
        mesh.materials.append(material)
        obj = bpy.data.objects.new(name=name, object_data=mesh)
        bpy.context.collection.objects.link(obj)
        # Weights in steps of 0.05, so the group fills in a few batches.
        group = obj.vertex_groups.new(name="wind")
        steps = {}
        for index, weight in enumerate(self.weights):
            if weight > 0.0:
                steps.setdefault(round(weight * 20), []).append(index)
        for step, indices in steps.items():
            group.add(indices, step / 20, 'REPLACE')
        return obj


def ring(x, y, z, radius, sides, phase=0.0):
    return [(x + radius * math.cos(phase + 2 * math.pi * i / sides), y + radius * math.sin(phase + 2 * math.pi * i / sides), z) for i in range(sides)]


def frustum(x, y, z0, z1, r0, r1, sides, phase=0.0):
    # A tapered prism, or a cone when r1 is 0.
    verts = ring(x, y, z0, r0, sides, phase)
    faces = [list(reversed(range(sides)))]
    if r1 > 0:
        verts += ring(x, y, z1, r1, sides, phase)
        faces += [[i, (i + 1) % sides, sides + (i + 1) % sides, sides + i] for i in range(sides)]
        faces.append(list(range(sides, 2 * sides)))
    else:
        verts.append((x, y, z1))
        faces += [[i, (i + 1) % sides, sides] for i in range(sides)]
    return verts, faces


def blob(x, y, z, radius, rng, segments=6, rings=4, squash=1.0, roughness=0.15):
    # A lumpy low-poly sphere.
    def lump(px, py, pz):
        k = 1 + rng.uniform(-roughness, roughness)
        return (x + px * k, y + py * k, z + pz * k * squash)

    verts = [lump(0, 0, -radius)]
    for r in range(1, rings):
        angle = math.pi * r / rings - math.pi / 2
        verts += [lump(*v) for v in ring(0, 0, radius * math.sin(angle), radius * math.cos(angle), segments, r * 0.5)]
    verts.append(lump(0, 0, radius))
    top = len(verts) - 1
    faces = [[0, 1 + (i + 1) % segments, 1 + i] for i in range(segments)]
    for r in range(rings - 2):
        a, b = 1 + r * segments, 1 + (r + 1) * segments
        faces += [[a + i, a + (i + 1) % segments, b + (i + 1) % segments, b + i] for i in range(segments)]
    last = 1 + (rings - 2) * segments
    faces += [[last + i, last + (i + 1) % segments, top] for i in range(segments)]
    return verts, faces


def add_tuft(builder, x, y, z, height, color, rng, blades=3, width=0.04, lean=0.25):
    for _ in range(blades):
        angle = rng.uniform(0, 2 * math.pi)
        h = height * rng.uniform(0.7, 1.1)
        dx, dy = math.cos(angle) * width, math.sin(angle) * width
        tip = (x + rng.uniform(-lean, lean) * h, y + rng.uniform(-lean, lean) * h, z + h)
        builder.add([(x - dx, y - dy, z), (x + dx, y + dy, z), tip], [[0, 1, 2]], color, base=z, height=h)


def add_flower(builder, x, y, z, height, color, rng):
    add_tuft(builder, x, y, z, height, (0.2, 0.55, 0.1), rng, blades=1, lean=0.1)
    verts, faces = blob(x, y, z + height, 0.07, rng, segments=5, rings=3)
    builder.add(verts, faces, color, jitter=0.05, base=z, height=height)


def add_conifer(builder, x, y, z, size, rng):
    total = 3.2 * size
    phase = rng.uniform(0, math.pi)
    verts, faces = frustum(x, y, z - 0.2, z + 0.8 * size, 0.18 * size, 0.12 * size, 6, phase)
    builder.add(verts, faces, (0.35, 0.2, 0.08), base=z, height=total)
    green = vary((0.05, 0.4, 0.15), 0.06, rng)
    for tier in range(3):
        bottom = z + (0.6 + 0.75 * tier) * size
        verts, faces = frustum(x, y, bottom, bottom + 1.4 * size, (1.0 - 0.25 * tier) * size, 0.0, 7, phase + tier)
        builder.add(verts, faces, green, base=z, height=total)


def add_broadleaf(builder, x, y, z, size, rng, palette=((0.2, 0.6, 0.1), (0.35, 0.7, 0.1), (0.1, 0.5, 0.15))):
    total = 3.5 * size
    verts, faces = frustum(x, y, z - 0.2, z + 1.6 * size, 0.2 * size, 0.13 * size, 6, rng.uniform(0, math.pi))
    builder.add(verts, faces, (0.4, 0.25, 0.12), base=z, height=total)
    color = rng.choice(palette)
    for _ in range(rng.randint(2, 3)):
        cx = x + rng.uniform(-0.5, 0.5) * size
        cy = y + rng.uniform(-0.5, 0.5) * size
        cz = z + rng.uniform(2.2, 2.8) * size
        verts, faces = blob(cx, cy, cz, rng.uniform(0.8, 1.1) * size, rng, squash=0.85)
        builder.add(verts, faces, color, jitter=0.06, base=z, height=total)


def add_bush(builder, x, y, z, size, color, rng):
    verts, faces = blob(x, y, z + 0.3 * size, size, rng, squash=0.7, roughness=0.25)
    builder.add(verts, faces, color, jitter=0.06, base=z - 0.2, height=1.6 * size)


def add_rock(builder, x, y, z, size, rng):
    verts, faces = blob(x, y, z, size, rng, segments=5, rings=3, squash=0.6, roughness=0.3)
    builder.add(verts, faces, vary((0.5, 0.5, 0.52), 0.08, rng), jitter=0.05)


def add_terrain(builder, size, cells, height, color):
    # A triangulated grid; height(x, y) gives the ground, color(z, slope)
    # the flat colour of each triangle.
    step = size / cells
    n = cells + 1
    verts = []
    for j in range(n):
        for i in range(n):
            x, y = -size / 2 + i * step, -size / 2 + j * step
            verts.append((x, y, height(x, y)))
    faces = []
    for j in range(cells):
        for i in range(cells):
            a, b, c, d = j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i
            faces += [[a, b, c], [a, c, d]] if (i + j) % 2 else [[a, b, d], [b, c, d]]
    offset = len(builder.verts)
    builder.verts += verts
    builder.weights += [0.0] * len(verts)
    for face in faces:
        p = [Vector(verts[k]) for k in face]
        normal = (p[1] - p[0]).cross(p[2] - p[0]).normalized()
        builder.faces.append([offset + k for k in face])
        builder.colors.append(vary(color(sum(v.z for v in p) / 3, 1 - abs(normal.z)), 0.03, builder.rng))


def scatter(rng, count, radius, keep=lambda x, y: True, spacing=0.0):
    # Points spread evenly over a disc, where keep(x, y) allows, optionally
    # at least spacing apart.
    points = []
    for _ in range(count * 20):
        if len(points) == count:
            break
        r = radius * math.sqrt(rng.random())
        angle = rng.uniform(0, 2 * math.pi)
        x, y = r * math.cos(angle), r * math.sin(angle)
        if not keep(x, y):
            continue
        if spacing and any((x - px) ** 2 + (y - py) ** 2 < spacing ** 2 for px, py in points):
            continue
        points.append((x, y))
    return points


def add_mover(name, velocity):
    # An empty sliding at a constant speed (metres per frame).
    mover = bpy.data.objects.new(name=name, object_data=None)
    bpy.context.collection.objects.link(mover)
    for axis, speed in enumerate(velocity):
        if speed:
            mover.driver_add("location", axis).driver.expression = f"frame * {speed}"
    return mover


def add_displace(obj, mover, size, strength, direction, mid_level, group="wind"):
    # Cloud noise dragged along by the mover displaces the (weighted) vertices.
    texture = bpy.data.textures.new(name=f"{obj.name}.{len(obj.modifiers)}", type='CLOUDS')
    texture.noise_scale = size
    modifier = obj.modifiers.new(name="Displace", type='DISPLACE')
    modifier.texture = texture
    modifier.texture_coords = 'OBJECT'
    modifier.texture_coords_object = mover
    modifier.direction = direction
    modifier.strength = strength
    modifier.mid_level = mid_level
    if group:
        modifier.vertex_group = group
    return modifier


def add_wind(obj, gusts, flutter, strength):
    # Big gusts lean everything downwind (+X) and roll across the land;
    # a faster, finer flutter shakes it sideways.
    add_displace(obj, gusts, size=6.0, strength=strength, direction='X', mid_level=0.25)
    add_displace(obj, flutter, size=1.2, strength=0.3 * strength, direction='Y', mid_level=0.5)


def add_orbit_camera(target, distance, height, start, sweep, lens=35):
    # Turns sweep degrees around the target over the timeline, starting at start.
    frames = bpy.context.scene.frame_end
    pivot = bpy.data.objects.new(name="CameraPivot", object_data=None)
    bpy.context.collection.objects.link(pivot)
    pivot.location = target
    pivot.driver_add("rotation_euler", 2).driver.expression = (
        f"{math.radians(start)} + frame / {frames} * {math.radians(sweep)}"
    )
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = lens
    camera_data.clip_end = 500
    camera = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera)
    camera.parent = pivot
    camera.location = (0, -distance, height)
    focus = bpy.data.objects.new(name="Focus", object_data=None)
    bpy.context.collection.objects.link(focus)
    focus.location = target
    track = camera.constraints.new(type='TRACK_TO')
    track.target = focus
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    bpy.context.scene.camera = camera
    return camera
