import math

import bmesh
import bpy
from mathutils import Vector

# 2D reference: inkscape-scripts/scripts/cyberpunk-butterfly00/butterfly00.py
# Its pixel coordinates are kept and mapped onto the 3D butterfly, which lies
# in the XY plane with the head towards +Y and the wings flapping around Y.
CENTER_X = 960
CENTER_Y = 430
HORIZON = 680
SCALE = 0.004  # meters per reference pixel

FPS = 30
SECONDS = 10
FRAMES = FPS * SECONDS

FLAPS_PER_SECOND = 3
WING_BEND = 0.35  # tip height (m) per square meter of span at full bend

SUN_DISTANCE = 300
SUN_RADIUS = 40
GRID_CELL = 4.0


def to_3d(point, z=0.0):
    x, y = point
    return Vector(((x - CENTER_X) * SCALE, (CENTER_Y - y) * SCALE, z))


def color(hex_color, alpha=1.0):
    """Hex sRGB to the linear RGBA that node sockets expect."""
    def linear(channel):
        channel /= 255
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4
    return tuple(linear(int(hex_color[i:i + 2], 16)) for i in (1, 3, 5)) + (alpha,)


def clear_scene():
    for collection in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                       bpy.data.cameras, bpy.data.lights, bpy.data.curves):
        for block in list(collection):
            collection.remove(block)


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.fps = FPS
    scene.render.fps_base = 1
    scene.frame_start = 1
    scene.frame_end = FRAMES
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = 16
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    return scene


# --- nodes -----------------------------------------------------------------

def node(tree, kind, inputs=(), **properties):
    """Inputs are (socket, value) pairs; a value that is a socket gets
    linked, anything else becomes the socket's default value."""
    new = tree.nodes.new(kind)
    for name, value in properties.items():
        setattr(new, name, value)
    for socket, value in inputs:
        socket = new.inputs[socket]
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return new


def math_node(tree, operation, a, b=0.0, c=0.0):
    return node(tree, "ShaderNodeMath", [(0, a), (1, b), (2, c)],
                operation=operation).outputs[0]


def map_range(tree, value, from_min, from_max, to_min=0.0, to_max=1.0,
              interpolation='LINEAR'):
    return node(tree, "ShaderNodeMapRange",
                [("Value", value), ("From Min", from_min),
                 ("From Max", from_max), ("To Min", to_min),
                 ("To Max", to_max)],
                interpolation_type=interpolation).outputs[0]


def mix_color(tree, factor, a, b):
    mix = node(tree, "ShaderNodeMix", data_type='RGBA', clamp_factor=True)
    for index, value in ((0, factor), (6, a), (7, b)):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, mix.inputs[index])
        else:
            mix.inputs[index].default_value = value
    return mix.outputs[2]


def new_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    return material, tree


def emission_material(name, surface_color, strength):
    """Glowing surface that still catches some light, so shapes read in 3D."""
    material, tree = new_material(name)
    shader = node(tree, "ShaderNodeBsdfPrincipled",
                  [("Base Color", surface_color), ("Roughness", 0.35),
                   ("Emission Color", surface_color),
                   ("Emission Strength", strength)])
    output = node(tree, "ShaderNodeOutputMaterial")
    tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return material


def gradient_material(name, coordinate, low, high, start, end, strength):
    """Object space gradient along one axis ("X", "Y" or "Z")."""
    material, tree = new_material(name)
    coordinates = node(tree, "ShaderNodeTexCoord")
    axes = node(tree, "ShaderNodeSeparateXYZ",
                [(0, coordinates.outputs["Object"])])
    factor = map_range(tree, axes.outputs[coordinate], start, end)
    surface = mix_color(tree, factor, color(low), color(high))
    shader = node(tree, "ShaderNodeBsdfPrincipled",
                  [("Base Color", surface), ("Roughness", 0.3),
                   ("Emission Color", surface),
                   ("Emission Strength", strength)])
    output = node(tree, "ShaderNodeOutputMaterial")
    tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return material


def wing_material():
    """The radial cyan to violet gradient with the pink-yellow spots, laid out
    in the left wing's UV space, which holds its 3D XY coordinates."""
    material, tree = new_material("Wing")
    uv = node(tree, "ShaderNodeUVMap").outputs[0]

    distance = node(tree, "ShaderNodeVectorMath", [(0, uv)],
                    operation='LENGTH').outputs["Value"]
    surface = mix_color(tree, math_node(tree, 'DIVIDE', distance, 480 * SCALE),
                        color("#00f0ff"), color("#7a00ff"))

    for x, y, size in ((-330, -190, 90), (-200, -90, 60), (-250, 170, 70)):
        center = to_3d((CENTER_X + x, CENTER_Y + y))
        offset = node(tree, "ShaderNodeVectorMath",
                      [(0, uv), (1, (center.x, center.y, 0.0))],
                      operation='DISTANCE').outputs["Value"]
        spot = math_node(tree, 'DIVIDE', offset, size / 2 * SCALE)
        surface = mix_color(tree, math_node(tree, 'LESS_THAN', spot, 1.0),
                            surface,
                            mix_color(tree, spot, color("#ff2975"),
                                      color("#ffd319")))

    shader = node(tree, "ShaderNodeBsdfPrincipled",
                  [("Base Color", surface), ("Roughness", 0.25),
                   ("Emission Color", surface), ("Emission Strength", 1.1)])
    output = node(tree, "ShaderNodeOutputMaterial")
    tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return material


def ground_material():
    """Dark floor with a glowing magenta grid fading into the distance."""
    material, tree = new_material("Ground")
    coordinates = node(tree, "ShaderNodeTexCoord")
    axes = node(tree, "ShaderNodeSeparateXYZ",
                [(0, coordinates.outputs["Object"])])
    view = node(tree, "ShaderNodeCameraData").outputs["View Distance"]

    def line_distance(axis):
        cells = math_node(tree, 'DIVIDE', axes.outputs[axis], GRID_CELL)
        within = math_node(tree, 'FRACT', math_node(tree, 'ADD', cells, 0.5))
        offset = math_node(tree, 'ABSOLUTE',
                           math_node(tree, 'SUBTRACT', within, 0.5))
        return math_node(tree, 'MULTIPLY', offset, GRID_CELL)

    nearest = math_node(tree, 'MINIMUM', line_distance("X"), line_distance("Y"))
    # lines get wider further away so they don't break up into dots
    width = math_node(tree, 'MULTIPLY_ADD', view, 0.0012, 0.035)
    line = map_range(tree, nearest, math_node(tree, 'MULTIPLY', width, 0.5),
                     width, 1.0, 0.0, 'SMOOTHSTEP')
    line = math_node(tree, 'MULTIPLY', line, map_range(tree, view, 30, 260,
                                                       1.0, 0.0))

    floor = mix_color(tree, map_range(tree, view, 0, 350),
                      color("#020008"), color("#12002a"))
    surface = mix_color(tree, line, floor, color("#ff00ff"))
    shader = node(tree, "ShaderNodeEmission",
                  [("Color", surface),
                   ("Strength", math_node(tree, 'MULTIPLY_ADD', line, 2.5,
                                          1.0))])
    output = node(tree, "ShaderNodeOutputMaterial")
    tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return material


def add_sky():
    world = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    direction = node(tree, "ShaderNodeTexCoord").outputs["Generated"]
    height = node(tree, "ShaderNodeSeparateXYZ", [(0, direction)]).outputs["Z"]
    sky = mix_color(tree, map_range(tree, height, 0.0, 0.45),
                    color("#3b0a5c"), color("#05010f"))
    background = node(tree, "ShaderNodeBackground", [("Color", sky)])
    output = node(tree, "ShaderNodeOutputWorld")
    tree.links.new(background.outputs[0], output.inputs["Surface"])
    return world


def add_bloom(scene):
    """The neon glow of the reference's blur filters."""
    tree = bpy.data.node_groups.new("Bloom", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out='OUTPUT',
                              socket_type='NodeSocketColor')
    layers = tree.nodes.new("CompositorNodeRLayers")
    glare = tree.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = 'Bloom'
    glare.inputs["Quality"].default_value = 'High'
    glare.inputs["Threshold"].default_value = 0.5
    glare.inputs["Strength"].default_value = 1.0
    glare.inputs["Size"].default_value = 0.6
    output = tree.nodes.new("NodeGroupOutput")
    tree.links.new(layers.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"], output.inputs[0])
    scene.compositing_node_group = tree
    scene.render.use_compositing = True


# --- geometry --------------------------------------------------------------

def bezier(start, control1, control2, end, steps):
    points = []
    for step in range(1, steps + 1):
        t = step / steps
        u = 1 - t
        points.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c
                            + t ** 3 * d
                            for a, b, c, d in zip(start, control1, control2,
                                                  end)))
    return points


def sample_stroke(stroke, steps=24):
    start, *segments = stroke
    points = [start]
    for segment in segments:
        points += bezier(points[-1], *segment, steps)
    return points


def new_object(name, mesh, parent=None, material=None):
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    if material:
        mesh.materials.append(material)
    return obj


def add_tube(bm, points, radius, closed=False, sides=6, material_index=0):
    """Round tube through 3D points, for the outlines, veins and antennae."""
    count = len(points)
    rings = []
    for index, point in enumerate(points):
        before = points[(index - 1) % count if closed else max(index - 1, 0)]
        after = points[(index + 1) % count if closed
                       else min(index + 1, count - 1)]
        tangent = (after - before).normalized()
        up = Vector((0, 0, 1)) if abs(tangent.z) < 0.9 else Vector((1, 0, 0))
        side = tangent.cross(up).normalized()
        up = side.cross(tangent)
        rings.append([bm.verts.new(point + radius * (math.cos(angle) * side
                                                     + math.sin(angle) * up))
                      for angle in (2 * math.pi * i / sides
                                    for i in range(sides))])
    for index in range(count if closed else count - 1):
        ring, following = rings[index], rings[(index + 1) % count]
        for i in range(sides):
            j = (i + 1) % sides
            face = bm.faces.new((ring[i], ring[j], following[j], following[i]))
            face.material_index = material_index
            face.smooth = True


def wing_outlines():
    upper = [(CENTER_X - 12, CENTER_Y - 20),
             ((CENTER_X - 120, CENTER_Y - 260), (CENTER_X - 420, CENTER_Y - 330),
              (CENTER_X - 470, CENTER_Y - 230)),
             ((CENTER_X - 520, CENTER_Y - 120), (CENTER_X - 330, CENTER_Y + 20),
              (CENTER_X - 12, CENTER_Y + 10))]
    lower = [(CENTER_X - 12, CENTER_Y + 20),
             ((CENTER_X - 260, CENTER_Y + 30), (CENTER_X - 400, CENTER_Y + 170),
              (CENTER_X - 330, CENTER_Y + 260)),
             ((CENTER_X - 260, CENTER_Y + 340), (CENTER_X - 90, CENTER_Y + 230),
              (CENTER_X - 12, CENTER_Y + 60))]
    return [upper, lower]


def wing_mesh(name, outline, side):
    """Membrane, glowing rim and vein of one wing, with a "Bend" shape key
    that curls the tip up (positive) or down (negative)."""
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new()

    rim = [to_3d(point) for point in sample_stroke(outline)[:-1]]
    membrane = bm.faces.new([bm.verts.new(point) for point in rim])
    bmesh.ops.triangulate(bm, faces=[membrane], ngon_method='BEAUTY')
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3,
                              use_grid_fill=True)

    start, (_, _, tip), _ = outline
    add_tube(bm, rim, 2.5 * SCALE, closed=True, material_index=1)
    add_tube(bm, [to_3d(start).lerp(to_3d(tip), t / 16) for t in range(17)],
             1.2 * SCALE, material_index=1)

    for face in bm.faces:
        for loop in face.loops:
            loop[uv_layer].uv = loop.vert.co.xy
    if side > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        for vert in bm.verts:
            vert.co.x = -vert.co.x

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def add_wing(name, outline, side, parent, materials, height):
    obj = new_object(name, wing_mesh(name, outline, side), parent)
    for material in materials:
        obj.data.materials.append(material)
    obj.location.z = height

    obj.shape_key_add(name="Basis")
    bend = obj.shape_key_add(name="Bend", from_mix=False)
    bend.slider_min = -1.0
    for point, vert in zip(bend.data, obj.data.vertices):
        point.co.z += WING_BEND * vert.co.x ** 2
    return obj


def ellipsoid(name, radii, segments=32, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings,
                              radius=1.0)
    bmesh.ops.scale(bm, vec=radii, verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.shade_smooth()
    return mesh


def add_body(parent):
    body = new_object("Body", ellipsoid("Body", (16 * SCALE, 130 * SCALE,
                                                 16 * SCALE)), parent,
                      gradient_material("Body", "Y", "#ff2975", "#ffffff",
                                        -130 * SCALE, 130 * SCALE, 1.2))
    body.location = to_3d((CENTER_X, CENTER_Y + 40))

    head = new_object("Head", ellipsoid("Head", (24 * SCALE,) * 3), parent,
                      gradient_material("Head", "Y", "#ff2975", "#ffffff",
                                        -24 * SCALE, 24 * SCALE, 1.4))
    head.location = to_3d((CENTER_X, CENTER_Y - 106))

    antenna = [(CENTER_X - 8, CENTER_Y - 125),
               ((CENTER_X - 30, CENTER_Y - 200), (CENTER_X - 90, CENTER_Y - 250),
                (CENTER_X - 130, CENTER_Y - 250))]
    bm = bmesh.new()
    for side in (1, -1):
        points = []
        for x, y in sample_stroke(antenna):
            point = to_3d((CENTER_X + side * (x - CENTER_X), y))
            point.z = (CENTER_Y - 110 - y) * SCALE * 0.7
            points.append(point)
        add_tube(bm, points, 2 * SCALE)
        knob = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8,
                                         radius=5 * SCALE)
        bmesh.ops.translate(bm, vec=points[-1], verts=knob["verts"])
    mesh = bpy.data.meshes.new("Antennae")
    bm.to_mesh(mesh)
    bm.free()
    mesh.shade_smooth()
    new_object("Antennae", mesh, parent,
               emission_material("Antennae", color("#ff2975"), 2.0))
    return body


def add_butterfly():
    butterfly = bpy.data.objects.new("Butterfly", None)
    bpy.context.collection.objects.link(butterfly)
    butterfly.rotation_mode = 'YXZ'

    materials = (wing_material(),
                 emission_material("Wing Rim", color("#e0ffff"), 3.0))
    upper, lower = wing_outlines()
    wings = []
    for side, suffix in ((-1, "L"), (1, "R")):
        wings.append((add_wing("Upper Wing " + suffix, upper, side, butterfly,
                               materials, 0.0), side, 0.0))
        wings.append((add_wing("Lower Wing " + suffix, lower, side, butterfly,
                               materials, -0.01), side, 0.5))
    add_body(butterfly)
    return butterfly, wings


def add_sun():
    """Disc on the horizon with the reference's stripes cut out of it."""
    unit = SUN_RADIUS / 300  # meters per reference pixel at the sun
    center_y = HORIZON - 60

    bands = []
    top = center_y - 300
    for gap_top, gap in sorted((HORIZON - 40 - i * 34, 4 + 3 * i)
                               for i in range(7)):
        bands.append((top, gap_top))
        top = gap_top + gap
    bands.append((top, HORIZON))

    bm = bmesh.new()
    for band_top, band_bottom in bands:
        high = min((center_y - band_top) * unit, SUN_RADIUS * 0.9999)
        low = (center_y - band_bottom) * unit
        heights = [high + (low - high) * i / 24 for i in range(25)]
        right = [(math.sqrt(SUN_RADIUS ** 2 - z * z), z) for z in heights]
        outline = right + [(-x, z) for x, z in reversed(right)]
        face = bm.faces.new([bm.verts.new((x, 0, z)) for x, z in outline])
        bmesh.ops.triangulate(bm, faces=[face], ngon_method='BEAUTY')
    mesh = bpy.data.meshes.new("Sun")
    bm.to_mesh(mesh)
    bm.free()

    sun = new_object("Sun", mesh, material=gradient_material(
        "Sun", "Z", "#ff2975", "#ffd319", -60 * unit, 240 * unit, 3.0))
    sun.location = (0, SUN_DISTANCE, 60 * unit)
    return sun


def add_ground():
    size = SUN_DISTANCE * 3
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(-size, -size, 0), (size, -size, 0), (size, size, 0),
                      (-size, size, 0)], [], [(0, 1, 2, 3)])
    return new_object("Ground", mesh, material=ground_material())


def add_light(name, kind, rotation, energy, light_color):
    light = bpy.data.lights.new(name, kind)
    light.energy = energy
    light.color = light_color[:3]
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler = rotation
    return obj


def add_camera():
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.collection.objects.link(camera)
    camera.data.lens = 30
    camera.data.clip_end = SUN_DISTANCE * 5
    bpy.context.scene.camera = camera
    return camera


# --- animation -------------------------------------------------------------

def flight_path(t):
    """A figure eight above the grid that loops every SECONDS."""
    u = 2 * math.pi * t / SECONDS
    return Vector((8 * math.sin(u), 4 * math.sin(2 * u),
                   3.2 + 0.8 * math.sin(3 * u)))


def smoothed_path(t, window=0.6, samples=13):
    return sum((flight_path(t + window * (i / (samples - 1) - 0.5))
                for i in range(samples)), Vector()) / samples


def animate(butterfly, wings, camera):
    dt = 1 / FPS
    yaw = None
    camera_rotation = None
    for frame in range(1, FRAMES + 1):
        t = (frame - 1) / FPS
        phase = 2 * math.pi * FLAPS_PER_SECOND * t

        # body follows the path, heading along it and banking into turns
        position = flight_path(t)
        velocity = (flight_path(t + dt) - flight_path(t - dt)) / (2 * dt)
        acceleration = (flight_path(t + dt) - 2 * position
                        + flight_path(t - dt)) / (dt * dt)
        heading = math.atan2(-velocity.x, velocity.y)
        if yaw is not None:
            heading += 2 * math.pi * round((yaw - heading) / (2 * math.pi))
        yaw = heading
        speed = velocity.xy.length
        turn = (velocity.x * acceleration.y
                - velocity.y * acceleration.x) / max(speed, 1e-6)
        bank = -0.5 * math.atan(turn / 9.81)
        pitch = math.radians(12) + math.atan2(velocity.z, speed)

        # each downstroke lifts the body a little
        butterfly.location = position + Vector((0, 0, -0.08 * math.sin(phase)))
        butterfly.rotation_euler = (pitch + 0.06 * math.cos(phase), bank, yaw)
        butterfly.keyframe_insert("location", frame=frame)
        butterfly.keyframe_insert("rotation_euler", frame=frame)

        # wings flap around the body axis while their tips trail behind
        for wing, side, lag in wings:
            stroke = phase - lag
            angle = math.radians(18 + 48 * math.sin(stroke))
            wing.rotation_euler.y = -side * angle
            wing.keyframe_insert("rotation_euler", index=1, frame=frame)
            bend = wing.data.shape_keys.key_blocks["Bend"]
            bend.value = -0.45 * math.cos(stroke)
            bend.keyframe_insert("value", frame=frame)

        # camera trails the butterfly and swings around it
        u = 2 * math.pi * t / SECONDS
        target = smoothed_path(t)
        around = -math.pi / 2 + 1.0 * math.sin(u + 0.4)
        distance = 7.5 + 1.5 * math.sin(2 * u)
        camera.location = smoothed_path(t - 0.25) + Vector((
            distance * math.cos(around), distance * math.sin(around),
            1.2 + 0.8 * math.sin(u + 1.0)))
        look = (target - camera.location).to_track_quat('-Z', 'Y')
        camera_rotation = (look.to_euler('XYZ', camera_rotation)
                           if camera_rotation else look.to_euler('XYZ'))
        camera.rotation_euler = camera_rotation
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)


def butterfly00():
    clear_scene()
    scene = setup_scene()
    add_sky()
    add_bloom(scene)
    add_sun()
    add_ground()
    add_light("Sun Light", 'SUN', (math.radians(-70), 0, 0), 3.0,
              color("#ff7ac0"))
    add_light("Fill Light", 'SUN', (math.radians(30), math.radians(20), 0),
              1.5, color("#7af6ff"))
    butterfly, wings = add_butterfly()
    camera = add_camera()
    animate(butterfly, wings, camera)
    scene.frame_set(1)
