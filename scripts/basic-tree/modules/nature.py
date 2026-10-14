import math
import random

import bpy
from mathutils import Vector

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


def setup_stage(sun_elevation, sun_rotation, sun_energy=4.0, sky_strength=0.6, samples=32):
    # A physical sky plus a sun lamp at the given elevation and azimuth (degrees).
    clear_scene()
    set_timeline()
    scene = bpy.context.scene
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.eevee.taa_render_samples = samples
    tree = scene.world.node_tree
    sky = tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = 'MULTIPLE_SCATTERING'
    sky.sun_disc = False
    sky.sun_elevation = math.radians(sun_elevation)
    sky.sun_rotation = math.radians(sun_rotation)
    background = tree.nodes["Background"]
    tree.links.new(sky.outputs["Color"], background.inputs["Color"])
    background.inputs["Strength"].default_value = sky_strength
    bpy.ops.object.light_add(type='SUN', rotation=(math.radians(90 - sun_elevation), 0, math.radians(sun_rotation)))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = sun_energy
    sun.data.color = (1.0, 0.92, 0.8)
    sun.data.angle = math.radians(2)
    return sun


def overcast(color=(0.32, 0.35, 0.4), strength=1.0):
    # A flat grey sky in place of the clear one.
    background = bpy.context.scene.world.node_tree.nodes["Background"]
    for link in list(background.inputs["Color"].links):
        bpy.context.scene.world.node_tree.links.remove(link)
    background.inputs["Color"].default_value = (*color, 1.0)
    background.inputs["Strength"].default_value = strength


def clock(shader):
    # Seconds since the start, for shaders that move with time.
    value = shader.node("ShaderNodeValue")
    value.outputs[0].driver_add("default_value").driver.expression = f"frame / {FPS}"
    return value.outputs[0]


def add_glare(strength, kind="Bloom"):
    # A compositor glow around the brightest parts of the frame.
    tree = bpy.data.node_groups.new(name="Compositor", type="CompositorNodeTree")
    tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type="NodeSocketColor")
    layers = tree.nodes.new(type="CompositorNodeRLayers")
    glare = tree.nodes.new(type="CompositorNodeGlare")
    glare.inputs["Type"].default_value = kind
    glare.inputs["Strength"].default_value = strength
    output = tree.nodes.new(type="NodeGroupOutput")
    tree.links.new(layers.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"], output.inputs["Image"])
    bpy.context.scene.compositing_node_group = tree


class Shader:
    # A thin wrapper for building node materials: inputs may be plain values
    # or sockets of other nodes, which get linked.

    def __init__(self, name):
        self.material = bpy.data.materials.new(name=name)
        self.tree = self.material.node_tree
        self.bsdf = self.tree.nodes["Principled BSDF"]
        self.output = self.tree.nodes["Material Output"]

    def set(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, socket)
        elif isinstance(value, tuple) and len(value) == 3 and len(socket.default_value) == 4:
            socket.default_value = (*value, 1.0)
        else:
            socket.default_value = value

    def node(self, kind, inputs=None, **props):
        node = self.tree.nodes.new(kind)
        for name, value in props.items():
            setattr(node, name, value)
        for key, value in (inputs or {}).items():
            self.set(node.inputs[key], value)
        return node

    def math(self, operation, a, b=0.0):
        return self.node("ShaderNodeMath", {0: a, 1: b}, operation=operation).outputs[0]

    def mix(self, factor, a, b, blend='MIX'):
        return self.node("ShaderNodeMix", {0: factor, 6: a, 7: b}, data_type='RGBA', blend_type=blend).outputs[2]

    def ramp(self, factor, stops):
        node = self.node("ShaderNodeValToRGB", {"Fac": factor})
        elements = node.color_ramp.elements
        for i, (position, color) in enumerate(stops):
            element = elements[i] if i < 2 else elements.new(position)
            element.position = position
            element.color = (*color, 1.0)
        return node.outputs["Color"]

    def attribute(self, name):
        return self.node("ShaderNodeAttribute", attribute_name=name).outputs["Fac"]

    def uv(self):
        separate = self.node("ShaderNodeSeparateXYZ", {0: self.node("ShaderNodeUVMap").outputs[0]})
        return separate.outputs[0], separate.outputs[1]

    def coords(self, kind="Object", scale=(1, 1, 1)):
        source = self.node("ShaderNodeTexCoord").outputs[kind]
        return self.node("ShaderNodeMapping", {"Vector": source, "Scale": scale}).outputs[0]

    def noise(self, vector, scale, detail=4.0, roughness=0.5, distortion=0.0):
        return self.node("ShaderNodeTexNoise", {"Vector": vector, "Scale": scale, "Detail": detail,
                                                "Roughness": roughness, "Distortion": distortion})

    def voronoi(self, vector, scale, feature='F1', randomness=1.0):
        return self.node("ShaderNodeTexVoronoi", {"Vector": vector, "Scale": scale, "Randomness": randomness},
                         feature=feature)

    def bump(self, height, strength, distance=0.01, normal=None):
        inputs = {"Height": height, "Strength": strength, "Distance": distance}
        if normal:
            inputs["Normal"] = normal
        return self.node("ShaderNodeBump", inputs).outputs["Normal"]

    def surface(self, color, roughness, normal=None, translucency=0.0, **extra):
        # Principled BSDF, optionally mixed with light shining through from behind.
        self.set(self.bsdf.inputs["Base Color"], color)
        self.set(self.bsdf.inputs["Roughness"], roughness)
        if normal:
            self.set(self.bsdf.inputs["Normal"], normal)
        for name, value in extra.items():
            self.set(self.bsdf.inputs[name.replace("_", " ")], value)
        if translucency:
            translucent = self.node("ShaderNodeBsdfTranslucent", {"Color": color})
            if normal:
                self.set(translucent.inputs["Normal"], normal)
            shader = self.node("ShaderNodeMixShader", {0: translucency, 1: self.bsdf.outputs[0], 2: translucent.outputs[0]})
            self.tree.links.new(shader.outputs[0], self.output.inputs["Surface"])
        return self.material


class Nodes:
    # A thin wrapper for building geometry node groups: inputs may be plain
    # values or sockets of other nodes, which get linked.

    def __init__(self, name):
        self.group = bpy.data.node_groups.new(name, 'GeometryNodeTree')

    def socket(self, name, kind, in_out='INPUT', default=None):
        item = self.group.interface.new_socket(name=name, in_out=in_out, socket_type=kind)
        if default is not None:
            item.default_value = default
        return item

    def set(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.group.links.new(value, socket)
        elif isinstance(value, (int, float)) and socket.type == 'VECTOR':
            socket.default_value = (value, value, value)
        else:
            socket.default_value = value

    def node(self, kind, inputs=None, **props):
        node = self.group.nodes.new(kind)
        for key, value in props.items():
            setattr(node, key, value)
        for key, value in (inputs or {}).items():
            self.set(node.inputs[key], value)
        return node

    def math(self, operation, a, b=0.0):
        return self.node("ShaderNodeMath", {0: a, 1: b}, operation=operation).outputs[0]

    def vector(self, operation, a, b=(0, 0, 0), scale=None):
        node = self.node("ShaderNodeVectorMath", {0: a, 1: b}, operation=operation)
        if scale is not None:
            self.set(node.inputs["Scale"], scale)
        return node.outputs[0]

    def attribute(self, name, data_type='FLOAT'):
        return self.node("GeometryNodeInputNamedAttribute", {"Name": name}, data_type=data_type).outputs["Attribute"]


def modifier_inputs(modifier):
    # The node group's inputs on a geometry nodes modifier, by name.
    return {item.name: getattr(modifier.properties.inputs, item.identifier)
            for item in modifier.node_group.interface.items_tree if item.in_out == 'INPUT'}


class MeshBuilder:
    # Collects pieces into one mesh, with per-corner UVs, per-face materials,
    # per-vertex float and colour attributes and vertex groups.

    def __init__(self, attributes=(), groups=(), colors=()):
        self.verts, self.faces, self.uvs, self.materials = [], [], [], []
        self.attributes = {name: [] for name in attributes}
        self.groups = {name: [] for name in groups}
        self.colors = {name: [] for name in colors}

    def add(self, verts, faces, uvs=None, material=0, **values):
        # values holds a number (an RGB tuple for colours) or a per-vertex list
        # for each attribute, group and colour; material may also be a per-face list.
        offset = len(self.verts)
        self.verts += verts
        for name, store in (*self.attributes.items(), *self.groups.items()):
            value = values.get(name, 0.0)
            store += value if isinstance(value, list) else [value] * len(verts)
        for name, store in self.colors.items():
            value = values.get(name, (0.0, 0.0, 0.0))
            store += value if isinstance(value, list) else [value] * len(verts)
        for i, face in enumerate(faces):
            self.faces.append([offset + k for k in face])
            self.materials.append(material[i] if isinstance(material, list) else material)
            self.uvs += uvs[i] if uvs else [(0.0, 0.0)] * len(face)

    def build(self, name, materials, smooth=True):
        mesh = bpy.data.meshes.new(name=name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.uv_layers.new(name="UVMap").data.foreach_set("uv", [c for uv in self.uvs for c in uv])
        mesh.polygons.foreach_set("material_index", self.materials)
        mesh.polygons.foreach_set("use_smooth", [smooth] * len(self.faces))
        for material in materials:
            mesh.materials.append(material)
        for attribute, values in self.attributes.items():
            mesh.attributes.new(name=attribute, type='FLOAT', domain='POINT').data.foreach_set("value", values)
        for attribute, values in self.colors.items():
            layer = mesh.color_attributes.new(name=attribute, type='FLOAT_COLOR', domain='POINT')
            layer.data.foreach_set("color", [c for rgb in values for c in (*rgb, 1.0)])
        mesh.update()
        obj = bpy.data.objects.new(name=name, object_data=mesh)
        bpy.context.collection.objects.link(obj)
        # Weights in steps of 0.02, so each group fills in a few batches.
        for group_name, weights in self.groups.items():
            group = obj.vertex_groups.new(name=group_name)
            steps = {}
            for index, weight in enumerate(weights):
                if weight > 0.0:
                    steps.setdefault(round(min(weight, 1.0) * 50), []).append(index)
            for step, indices in steps.items():
                group.add(indices, step / 50, 'REPLACE')
        return obj


def grid(nx, ny, point):
    # A quad grid over (u, v) in [0, 1]^2; point(u, v) places each vertex.
    verts, faces, uvs = [], [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append(point(i / nx, j / ny))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append([a, a + 1, a + nx + 2, a + nx + 1])
            uvs.append([(i / nx, j / ny), ((i + 1) / nx, j / ny), ((i + 1) / nx, (j + 1) / ny), (i / nx, (j + 1) / ny)])
    return verts, faces, uvs


def add_blade(builder, rng, x, y, height, width, segments=4, lean=0.4, tint=0.0, material=0, crease=True, reach=None):
    # A grass blade: a tapering ribbon that arches over, folded along its midrib.
    # The "height" attribute runs from 0 at the root to 1 at the tip; the "wind"
    # weight grows with height above the ground, reaching 1 at reach metres.
    reach = reach or height
    bend = rng.uniform(0, 2 * math.pi)
    forward = Vector((math.cos(bend), math.sin(bend), 0.0))
    side = Vector((-forward.y, forward.x, 0.0))
    arch = lean * rng.uniform(0.5, 1.2)
    verts, heights = [], []
    columns = 3 if crease else 2
    for s in range(segments):
        t = s / segments
        centre = Vector((x, y, 0.0)) + forward * (arch * height * t * t) + Vector((0, 0, height * t * (1 - 0.3 * arch * t)))
        half = 0.5 * width * (1 - t ** 2.5) * (0.8 + 0.2 * math.sin(math.pi * min(t * 3, 1)))
        row = [centre - side * half, centre + forward * (0.3 * half) + Vector((0, 0, 0.3 * half)), centre + side * half]
        verts += row if crease else [row[0], row[2]]
        heights += [t] * columns
    tip = Vector((x, y, 0.0)) + forward * (arch * height) + Vector((0, 0, height * (1 - 0.3 * arch)))
    verts.append(tip)
    heights.append(1.0)
    us = (0.0, 0.5, 1.0) if crease else (0.0, 1.0)
    faces, uvs = [], []
    for s in range(segments - 1):
        for c in range(columns - 1):
            a = s * columns + c
            faces.append([a, a + 1, a + columns + 1, a + columns])
            uvs.append([(us[c], s / segments), (us[c + 1], s / segments), (us[c + 1], (s + 1) / segments), (us[c], (s + 1) / segments)])
    last = (segments - 1) * columns
    top = (segments - 1) / segments
    for c in range(columns - 1):
        faces.append([last + c, last + c + 1, len(verts) - 1])
        uvs.append([(us[c], top), (us[c + 1], top), (0.5, 1.0)])
    builder.add([tuple(v) for v in verts], faces, uvs, material=material, height=heights, tint=tint,
                wind=[min(max(v.z, 0.0) / reach, 1.0) ** 1.4 for v in verts])


def add_leaf(builder, base, forward, normal, length, width, material=0, rows=5, **values):
    # A leaf blade folded along its midrib; UV u runs across (0..1), v along it.
    forward = Vector(forward).normalized()
    normal = Vector(normal).normalized()
    side = forward.cross(normal).normalized()
    base = Vector(base)
    verts = []
    for r in range(rows):
        t = r / rows
        half = 0.5 * width * math.sin(math.pi * (0.1 + 0.9 * t)) ** 0.8 * (1.1 - 0.4 * t) if r else 0.05 * width
        centre = base + forward * (length * t) + normal * (0.15 * length * t * (1 - t))
        verts += [centre - side * half - normal * (0.2 * half), centre, centre + side * half - normal * (0.2 * half)]
    verts.append(base + forward * length)
    faces, uvs = [], []
    for r in range(rows - 1):
        for c in range(2):
            a = r * 3 + c
            faces.append([a, a + 1, a + 4, a + 3])
            uvs.append([(c / 2, r / rows), ((c + 1) / 2, r / rows), ((c + 1) / 2, (r + 1) / rows), (c / 2, (r + 1) / rows)])
    last = (rows - 1) * 3
    for c in range(2):
        faces.append([last + c, last + c + 1, len(verts) - 1])
        uvs.append([(c / 2, (rows - 1) / rows), ((c + 1) / 2, (rows - 1) / rows), (0.5, 1.0)])
    builder.add([tuple(v) for v in verts], faces, uvs, material=material, **values)


def add_mover(name, velocity):
    # An empty sliding at a constant speed (metres per frame).
    mover = bpy.data.objects.new(name=name, object_data=None)
    bpy.context.collection.objects.link(mover)
    for axis, speed in enumerate(velocity):
        if speed:
            mover.driver_add("location", axis).driver.expression = f"frame * {speed}"
    return mover


def add_displace(obj, mover, size, strength, direction, mid_level=0.5, group="wind", depth=2):
    # Cloud noise dragged along by the mover displaces the (weighted) vertices.
    texture = bpy.data.textures.new(name=f"{obj.name}.{len(obj.modifiers)}", type='CLOUDS')
    texture.noise_scale = size
    texture.noise_depth = depth
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


def add_wind(obj, gusts, flutter, size, strength, group="wind"):
    # Gusts rolling downwind (+X) lean everything over and press it down a
    # little; a faster, finer flutter shakes it sideways.
    add_displace(obj, gusts, size=size, strength=strength, direction='X', mid_level=0.2, group=group)
    add_displace(obj, gusts, size=size, strength=-0.35 * strength, direction='Z', mid_level=0.2, group=group)
    add_displace(obj, flutter, size=0.25 * size, strength=0.35 * strength, direction='Y', group=group)


def add_camera(location, target, lens=50, fstop=0.0):
    # A camera tracking an empty at target; fstop > 0 turns on depth of field
    # focused on the target.
    focus = bpy.data.objects.new(name="Focus", object_data=None)
    bpy.context.collection.objects.link(focus)
    focus.location = target
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = lens
    camera_data.clip_start = 0.01
    camera_data.clip_end = 500
    if fstop:
        camera_data.dof.use_dof = True
        camera_data.dof.focus_object = focus
        camera_data.dof.aperture_fstop = fstop
    camera = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = location
    track = camera.constraints.new(type='TRACK_TO')
    track.target = focus
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    bpy.context.scene.camera = camera
    return camera, focus


def keyframes(obj, path, frames):
    # frames maps frame numbers to values, eased in and out.
    for frame, value in frames.items():
        setattr(obj, path, value)
        obj.keyframe_insert(data_path=path, frame=frame)


def meadow_material():
    shader = Shader("Meadow")
    coords = shader.coords("Object")
    patches = shader.noise(coords, 0.5, detail=6.0, roughness=0.6).outputs["Fac"]
    color = shader.ramp(patches, [(0.35, (0.03, 0.05, 0.008)), (0.55, (0.07, 0.09, 0.015)), (0.7, (0.13, 0.11, 0.04))])
    fine = shader.noise(coords, 90.0, detail=4.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(fine, [(0.3, (0.6, 0.6, 0.6)), (0.7, (1.2, 1.2, 1.2))]), 'MULTIPLY')
    return shader.surface(color, 0.9, shader.bump(fine, 0.4))


def blade_material():
    shader = Shader("GrassBlade")
    height = shader.attribute("height")
    tint = shader.attribute("tint")
    color = shader.ramp(height, [(0.0, (0.025, 0.045, 0.006)), (1.0, (0.17, 0.24, 0.03))])
    color = shader.mix(1.0, color, shader.ramp(tint, [(0.0, (0.7, 0.9, 0.6)), (0.85, (1.0, 1.0, 1.0)), (1.0, (1.6, 1.3, 0.7))]), 'MULTIPLY')
    return shader.surface(color, 0.5, translucency=0.3)


def add_meadow(path_length, seed=11, blades=60000, height=(0.06, 0.2), near=1.5, falloff=2.0, spread=(-5.0, 14.0),
               strength=0.12):
    # Ground and grass along a path heading towards -Y, watched from -X: full
    # density within near metres of the path, thinning out over falloff
    # metres, across spread (x range); blades of the given height range,
    # swaying in the wind.
    rng = random.Random(seed)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, -path_length / 2, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(meadow_material())
    builder = MeshBuilder(attributes=("height", "tint"), groups=("wind",))
    placed = 0
    while placed < blades:
        x = rng.uniform(*spread)
        if rng.random() > 1 / (1 + (max(abs(x) - near, 0.0) / falloff) ** 2):
            continue
        y = rng.uniform(4.0, -path_length - 6.0)
        blade = rng.uniform(*height) * (1 + 0.03 * max(x, 0))
        add_blade(builder, rng, x, y, blade, blade * rng.uniform(0.04, 0.06), segments=3, tint=rng.random(),
                  crease=False, reach=1.5 * height[1])
        placed += 1
    grass = builder.build("Grass", [blade_material()])
    gusts = add_mover("Gusts", (0.12, 0.0, 0.0))
    flutter = add_mover("Flutter", (0.05, 0.0, 0.04))
    add_wind(grass, gusts, flutter, size=2.0, strength=strength)
    return grass


def rain_material(name, color, brightness, opacity):
    # Faint streaks that fade in and out along their length (UV v).
    shader = Shader(name)
    _, v = shader.uv()
    fade = shader.math('MULTIPLY', shader.math('SINE', shader.math('MULTIPLY', v, math.pi)), opacity)
    glow = shader.node("ShaderNodeEmission", {"Color": color, "Strength": brightness})
    clear = shader.node("ShaderNodeBsdfTransparent")
    mixed = shader.node("ShaderNodeMixShader", {0: fade, 1: clear.outputs[0], 2: glow.outputs[0]})
    shader.tree.links.new(mixed.outputs[0], shader.output.inputs["Surface"])
    shader.material.surface_render_method = 'DITHERED'
    return shader.material


def add_rain(box, height, count, speed=7.0, wind=(2.0, 0.5), length=0.5, width=0.004, splash=0.0,
             color=(0.75, 0.8, 0.85), brightness=0.6, opacity=0.35):
    # Raindrops falling through box ((x0, x1), (y0, y1)) from height to the
    # ground at speed (m/s), slanted by wind (m/s) that gusts as it goes;
    # with splash > 0, each lands in a little crown splash that big.
    # Built in geometry nodes, so every drop's fall is a function of time.
    drop = MeshBuilder()
    for angle in (0.0, math.pi / 2):
        dx, dy = 0.5 * math.cos(angle), 0.5 * math.sin(angle)
        drop.add([(-dx, -dy, -0.5), (dx, dy, -0.5), (dx, dy, 0.5), (-dx, -dy, 0.5)], [[0, 1, 2, 3]],
                 [[(0, 0), (1, 0), (1, 1), (0, 1)]])
    drop = drop.build("Raindrop", [rain_material("Rain", color, brightness, opacity)])
    crown = MeshBuilder()
    for k in range(8):
        a = 2 * math.pi * k / 8
        out, side = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0)) * 0.12
        crown.add([tuple(out * 0.3 - side), tuple(out * 0.3 + side), tuple(out + Vector((0, 0, 0.9)))], [[0, 1, 2]],
                  [[(0, 0), (1, 0), (0.5, 1)]])
    crown = crown.build("Splash", [rain_material("Splash", color, brightness, 2 * opacity)])
    for part in (drop, crown):
        part.hide_render = part.hide_viewport = True

    tree = Nodes("Rain")
    tree.socket("Geometry", 'NodeSocketGeometry', in_out='OUTPUT')
    node, math_node, vector = tree.node, tree.math, tree.vector
    (x0, x1), (y0, y1) = box
    points = node("GeometryNodePoints", {"Count": count})
    seed = node("FunctionNodeRandomValue", {0: (x0, y0, 0.0), 1: (x1, y1, 1.0)}, data_type='FLOAT_VECTOR').outputs[0]
    spot = node("ShaderNodeSeparateXYZ", {0: seed}).outputs
    seconds = node("GeometryNodeInputSceneTime").outputs["Seconds"]
    fallen = math_node('FLOORED_MODULO', math_node('ADD', math_node('MULTIPLY', spot[2], height), math_node('MULTIPLY', seconds, speed)), height)
    gust = node("ShaderNodeTexNoise", {"Vector": vector('SCALE', seed, scale=0.05), "W": math_node('MULTIPLY', seconds, 0.25),
                                       "Scale": 1.0, "Detail": 1.0}, noise_dimensions='4D').outputs["Factor"]
    blow = vector('SCALE', (wind[0], wind[1], 0.0), scale=math_node('ADD', 0.4, math_node('MULTIPLY', gust, 1.2)))
    drift = vector('SCALE', blow, scale=math_node('DIVIDE', fallen, speed))
    falling = node("ShaderNodeCombineXYZ", {0: spot[0], 1: spot[1], 2: math_node('SUBTRACT', height, fallen)}).outputs[0]
    placed = node("GeometryNodeSetPosition", {"Geometry": points.outputs[0], "Position": vector('ADD', falling, drift)})
    heading = node("FunctionNodeAlignRotationToVector", {"Vector": vector('ADD', blow, (0.0, 0.0, -speed))}, axis='Z').outputs[0]
    drops = node("GeometryNodeInstanceOnPoints", {"Points": placed.outputs[0], "Rotation": heading, "Scale": (width, width, length),
                                                  "Instance": node("GeometryNodeObjectInfo", {"Object": drop}).outputs["Geometry"]})
    joined = node("GeometryNodeJoinGeometry")
    tree.set(joined.inputs[0], drops.outputs[0])
    if splash:
        # A drop has just landed where its last fall ended.
        age = math_node('DIVIDE', fallen, speed)
        landed = node("ShaderNodeCombineXYZ", {0: spot[0], 1: spot[1], 2: 0.0}).outputs[0]
        landed = vector('ADD', landed, vector('SCALE', blow, scale=height / speed))
        fresh = math_node('LESS_THAN', age, 0.1)
        splashed = node("GeometryNodeSetPosition", {"Geometry": points.outputs[0], "Position": landed})
        size = math_node('MULTIPLY', splash, math_node('ADD', 0.3, math_node('MULTIPLY', age, 10.0)))
        splashes = node("GeometryNodeInstanceOnPoints", {"Points": splashed.outputs[0], "Selection": fresh, "Scale": size,
                                                         "Instance": node("GeometryNodeObjectInfo", {"Object": crown}).outputs["Geometry"]})
        tree.set(joined.inputs[0], splashes.outputs[0])
    tree.set(node("NodeGroupOutput").inputs[0], joined.outputs[0])
    rain = bpy.data.objects.new(name="Rain", object_data=bpy.data.meshes.new(name="Rain"))
    bpy.context.collection.objects.link(rain)
    rain.modifiers.new(name="Rain", type='NODES').node_group = tree.group
    return rain
