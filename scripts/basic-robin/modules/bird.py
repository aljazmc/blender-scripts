import math
import random

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from modules.nature import FPS, Shader, MeshBuilder, Nodes, modifier_inputs, add_mover, add_displace
from modules.body import (SIDES, lerp, smootherstep, add_armature, bind, rigid, surface_point, add_sphere,
                          add_tube, eye_material, turn, skin_mesh, add_follow_camera, rest_frames,
                          timeline_frames)

WING_BONES = ("arm", "forearm", "hand")


class Anatomy:
    # Joint positions for a perching bird facing -Y, standing on z = 0, worked
    # out from a few proportions (metres):
    #   length: breast to rump; radius: of the body; head: radius; neck: length
    #   beak: (length, base radius, droop); legs: (tarsus length, radius, toe length)
    #   tail: (length, width); wing: (arm, forearm, hand, chord)

    def __init__(self, length, radius, head, neck, beak, legs, tail, wing):
        self.length, self.radius, self.head_radius = length, radius, head
        self.beak, self.legs, self.tail, self.wing = beak, legs, tail, wing
        tarsus, _, _ = legs
        r = radius
        centre = tarsus + 0.95 * r
        j = self.joints = {}
        j["rump"] = Vector((0, 0.42 * length, centre + 0.1 * r))
        j["belly"] = Vector((0, 0.05 * length, centre - 0.05 * r))
        j["breast"] = Vector((0, -0.3 * length, centre + 0.1 * r))
        j["neck"] = Vector((0, -0.45 * length, centre + 0.6 * r))
        j["head"] = j["neck"] + Vector((0, -0.2 * neck, neck))
        j["beak"] = j["head"] + Vector((0, -0.8 * head, -0.15 * head))
        j["tip"] = j["beak"] + Vector((0, -beak[0], -beak[2]))
        j["tail"] = j["rump"] + Vector((0, 0.15 * length, 0.05 * r))
        j["tail.tip"] = j["tail"] + Vector((0, tail[0], -0.12 * tail[0]))
        arm, forearm, hand, _ = wing
        for side, s in SIDES:
            j[f"hip.{side}"] = Vector((0.4 * r * s, 0.05 * length, centre - 0.35 * r))
            j[f"ankle.{side}"] = Vector((0.35 * r * s, 0.12 * length, tarsus))
            j[f"foot.{side}"] = Vector((0.33 * r * s, 0.0, 0.6 * legs[1]))
            j[f"toes.{side}"] = j[f"foot.{side}"] + Vector((0, -legs[2], 0))
            j[f"shoulder.{side}"] = Vector((0.7 * r * s, -0.22 * length, centre + 0.5 * r))
            j[f"elbow.{side}"] = j[f"shoulder.{side}"] + Vector((arm * s, 0.25 * arm, 0))
            j[f"wrist.{side}"] = j[f"elbow.{side}"] + Vector((forearm * s, -0.1 * forearm, 0))
            j[f"wingtip.{side}"] = j[f"wrist.{side}"] + Vector((hand * s, 0.15 * hand, 0))

    def bones(self):
        # (name, head, tail, parent, radius at head, radius at tail); parents first.
        j, r = self.joints, self.radius
        bones = [
            ("body", j["rump"], j["breast"], None, 0.8 * r, r),
            ("neck", j["neck"], j["head"], "body", 0.6 * r, self.head_radius),
            ("head", j["head"], j["beak"], "neck", self.head_radius, 0.5 * self.head_radius),
            ("tail", j["tail"], j["tail.tip"], "body", 0.35 * r, 0.1 * r),
        ]
        leg_radius = self.legs[1]
        for side, _ in SIDES:
            bones += [
                (f"thigh.{side}", j[f"hip.{side}"], j[f"ankle.{side}"], "body", 0.3 * r, 1.5 * leg_radius),
                (f"tarsus.{side}", j[f"ankle.{side}"], j[f"foot.{side}"], f"thigh.{side}", leg_radius, leg_radius),
                (f"toes.{side}", j[f"foot.{side}"], j[f"toes.{side}"], f"tarsus.{side}", leg_radius, leg_radius),
                (f"arm.{side}", j[f"shoulder.{side}"], j[f"elbow.{side}"], "body", 0.2 * r, 0.12 * r),
                (f"forearm.{side}", j[f"elbow.{side}"], j[f"wrist.{side}"], f"arm.{side}", 0.12 * r, 0.08 * r),
                (f"hand.{side}", j[f"wrist.{side}"], j[f"wingtip.{side}"], f"forearm.{side}", 0.08 * r, 0.03 * r),
            ]
        return bones

    def skeleton(self):
        # The body the Skin modifier wraps: a plump egg with a round head.
        j, r = self.joints, self.radius
        nodes = [("rump", 0.6 * r), ("belly", r), ("breast", 0.95 * r), ("neck", 0.62 * r),
                 ("head", self.head_radius), ("tail", 0.3 * r)]
        names = [n for n, _ in nodes]
        edges = [("tail", "rump"), ("rump", "belly"), ("belly", "breast"), ("breast", "neck"), ("neck", "head")]
        return [(j[n], radius) for n, radius in nodes], [(names.index(a), names.index(b)) for a, b in edges]


def plumage_material(sheen=0.3, film=0.0):
    # One material for every feather: its colour, a paler fringe and a dark
    # shaft streak (all per feather), barbs, and a lighter rachis.
    shader = Shader("Plumage")
    color = shader.node("ShaderNodeAttribute", attribute_name="pcol").outputs["Color"]
    edge_color = shader.node("ShaderNodeAttribute", attribute_name="pedge").outputs["Color"]
    streak = shader.attribute("pstreak")
    chance = shader.attribute("prand")
    u, v = shader.uv()
    across = shader.math('MULTIPLY', shader.math('ABSOLUTE', shader.math('SUBTRACT', u, 0.5)), 2.0)
    fringe = shader.math('MAXIMUM', shader.node("ShaderNodeMapRange", {"Value": across, 1: 0.72, 2: 0.95}).outputs[0],
                         shader.node("ShaderNodeMapRange", {"Value": v, 1: 0.88, 2: 0.99}).outputs[0])
    color = shader.mix(fringe, color, edge_color)
    centre = shader.math('MULTIPLY', shader.math('LESS_THAN', across, 0.35), shader.math('LESS_THAN', v, 0.78))
    dark = shader.math('MULTIPLY', centre, shader.math('MULTIPLY', streak, shader.math('GREATER_THAN', chance, 0.35)))
    color = shader.mix(shader.math('MULTIPLY', dark, 0.85), color, (0.015, 0.01, 0.008))
    barbs = shader.math('SINE', shader.math('MULTIPLY', shader.math('SUBTRACT', v, shader.math('MULTIPLY', across, 0.6)), 140.0))
    rachis = shader.math('LESS_THAN', across, 0.05)
    color = shader.mix(shader.math('MULTIPLY', rachis, 0.5), color, shader.mix(1.0, color, (1.8, 1.8, 1.7), 'MULTIPLY'))
    shade = shader.ramp(barbs, [(0.0, (0.85, 0.85, 0.85)), (1.0, (1.05, 1.05, 1.05))])
    color = shader.mix(1.0, color, shade, 'MULTIPLY')
    tilt = shader.ramp(chance, [(0.0, (0.85, 0.85, 0.85)), (1.0, (1.1, 1.1, 1.1))])
    color = shader.mix(1.0, color, tilt, 'MULTIPLY')
    extra = {"Sheen_Weight": sheen, "Sheen_Tint": color, "Specular_IOR_Level": 0.25}
    if film:
        # Crow-black feathers flash blue and violet.
        extra["Thin_Film_Thickness"] = film
    return shader.surface(color, 0.65, shader.bump(barbs, 0.05, 0.0005), translucency=0.1, **extra)


def feather_outline(builder, base, forward, normal, length, width, rows=6, asymmetry=0.0, curve=0.0, **values):
    # A feather vane: rounded, tapering to its tip, optionally narrower on the
    # leading side and curving down; UV u runs across it, v along it. The
    # "wind" weight grows towards the tip.
    forward, normal = Vector(forward).normalized(), Vector(normal).normalized()
    side = forward.cross(normal).normalized()
    base = Vector(base)
    verts = []
    for r in range(rows + 1):
        t = r / rows
        half = 0.5 * width * math.sin(math.pi * (0.12 + 0.88 * t)) ** 0.5 * (1 - 0.25 * t)
        if r == rows:
            half = 0.0
        centre = base + forward * (length * t) - normal * (curve * length * t * t)
        verts += [centre - side * half * (1 - asymmetry), centre, centre + side * half * (1 + asymmetry)]
    faces, uvs = [], []
    for r in range(rows):
        for c in range(2):
            a = r * 3 + c
            faces.append([a, a + 1, a + 4, a + 3])
            uvs.append([(c / 2, r / rows), ((c + 1) / 2, r / rows), ((c + 1) / 2, (r + 1) / rows), (c / 2, (r + 1) / rows)])
    wind = [((k // 3) / rows) ** 1.5 for k in range(len(verts))]
    builder.add([tuple(v) for v in verts], faces, uvs, wind=wind, **values)


def feather_card():
    # The contour feather the plumage is tiled with: unit length along +Y,
    # lying in the XY plane, cupped slightly to hug the body.
    builder = MeshBuilder(groups=("wind",))
    feather_outline(builder, (0, 0, 0), (0, 1, 0), (0, 0, 1), 1.0, 0.8, rows=5, curve=0.08)
    card = builder.build("FeatherCard", [])
    card.hide_render = True
    card.hide_viewport = True
    return card


def plumage_nodes(body, card, material):
    # Geometry nodes tiling the posed body with overlapping contour feathers,
    # combed back, lifted by gusts and pressed flat (but shivering) in flight.
    tree = Nodes("Plumage")
    tree.socket("Coverage", 'NodeSocketFloat', default=5.0)
    tree.socket("Wind", 'NodeSocketFloat', default=1.0)
    tree.socket("Fly", 'NodeSocketFloat', default=0.0)
    tree.socket("Geometry", 'NodeSocketGeometry', in_out='OUTPUT')
    node, math, attribute = tree.node, tree.math, tree.attribute
    source = node("NodeGroupInput").outputs
    out = node("NodeGroupOutput")
    skin = node("GeometryNodeObjectInfo", {"Object": body}, transform_space='RELATIVE').outputs["Geometry"]
    size = attribute("psize")
    # Small feathers sit closer together, so the overlap stays the same.
    density = math('DIVIDE', source["Coverage"], math('MAXIMUM', math('MULTIPLY', size, size), 1e-6))
    points = node("GeometryNodeDistributePointsOnFaces", {"Mesh": skin, "Selection": math('GREATER_THAN', size, 0.0005),
                                                          "Density": density, "Seed": 5})
    facing = node("FunctionNodeAlignRotationToVector", {"Vector": points.outputs["Normal"]}, axis='Z').outputs[0]
    combed = node("FunctionNodeAlignRotationToVector", {"Rotation": facing, "Vector": (0.0, 1.0, -0.35)},
                  axis='Y', pivot_axis='Z').outputs[0]
    seconds = node("GeometryNodeInputSceneTime").outputs["Seconds"]
    position = node("GeometryNodeInputPosition").outputs[0]
    gust = node("ShaderNodeTexNoise", {"Vector": position, "W": math('MULTIPLY', seconds, 0.7), "Scale": 1.5, "Detail": 1.0},
                noise_dimensions='4D').outputs["Factor"]
    gust = math('MAXIMUM', math('MULTIPLY', math('SUBTRACT', gust, 0.4), 2.5), 0.0)
    shiver = node("ShaderNodeTexNoise", {"Vector": position, "W": math('MULTIPLY', seconds, 6.0), "Scale": 60.0, "Detail": 1.0},
                  noise_dimensions='4D').outputs["Factor"]
    calm = math('SUBTRACT', 1.0, math('MULTIPLY', source["Fly"], 0.7))
    lift = math('ADD', 0.12, math('MULTIPLY', math('MULTIPLY', gust, source["Wind"]), math('MULTIPLY', calm, 0.6)))
    lift = math('ADD', lift, math('MULTIPLY', math('SUBTRACT', shiver, 0.5), math('ADD', 0.25, math('MULTIPLY', source["Fly"], 0.35))))
    tilt = node("FunctionNodeEulerToRotation", {"Euler": node("ShaderNodeCombineXYZ", {0: lift}).outputs[0]}).outputs[0]
    ruffled = node("FunctionNodeRotateRotation", {"Rotation": combed, "Rotate By": tilt}, rotation_space='LOCAL').outputs[0]
    spread = node("FunctionNodeRandomValue", {"Min": 0.85, "Max": 1.15}).outputs[0]
    feather = node("GeometryNodeObjectInfo", {"Object": card}).outputs["Geometry"]
    placed = node("GeometryNodeInstanceOnPoints", {"Points": points.outputs["Points"], "Instance": feather,
                                                   "Rotation": ruffled, "Scale": math('MULTIPLY', size, spread)})
    chance = node("FunctionNodeRandomValue", {"Min": 0.0, "Max": 1.0, "Seed": 9}).outputs[0]
    tagged = node("GeometryNodeStoreNamedAttribute", {"Geometry": placed.outputs[0], "Name": "prand", "Value": chance},
                  data_type='FLOAT', domain='INSTANCE')
    realized = node("GeometryNodeRealizeInstances", {"Geometry": tagged.outputs[0]})
    dressed = node("GeometryNodeSetMaterial", {"Geometry": realized.outputs[0], "Material": material})
    tree.set(out.inputs[0], dressed.outputs[0])
    return tree.group


def add_plumage(body, main_bone, coat, features, material):
    # coat(position, normal, bone) -> (colour, fringe colour, streak 0..1,
    # feather length) for each vertex; feathers stay clear of the features.
    mesh = body.data
    colors, edges, streaks, sizes = [], [], [], []
    for vertex, bone in zip(mesh.vertices, main_bone):
        color, edge, streak, size = coat(vertex.co, vertex.normal, bone)
        for centre, clearance in features:
            size *= smootherstep(((vertex.co - centre).length - clearance) / (0.5 * clearance))
        colors += [*color, 1.0]
        edges += [*edge, 1.0]
        streaks.append(streak)
        sizes.append(size)
    mesh.color_attributes.new(name="pcol", type='FLOAT_COLOR', domain='POINT').data.foreach_set("color", colors)
    mesh.color_attributes.new(name="pedge", type='FLOAT_COLOR', domain='POINT').data.foreach_set("color", edges)
    mesh.attributes.new(name="pstreak", type='FLOAT', domain='POINT').data.foreach_set("value", streaks)
    mesh.attributes.new(name="psize", type='FLOAT', domain='POINT').data.foreach_set("value", sizes)
    mesh.materials.append(down_material())
    plumage = bpy.data.objects.new(name="Plumage", object_data=bpy.data.meshes.new(name="Plumage"))
    plumage.data.materials.append(material)
    bpy.context.collection.objects.link(plumage)
    modifier = plumage.modifiers.new(name="Plumage", type='NODES')
    modifier.node_group = plumage_nodes(body, feather_card(), material)
    return modifier_inputs(modifier)["Fly"]


def down_material():
    # The downy body under the contour feathers, in the same colours.
    shader = Shader("Down")
    color = shader.node("ShaderNodeAttribute", attribute_name="pcol").outputs["Color"]
    fluff = shader.noise(shader.coords("Object"), 800.0, detail=4.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(fluff, [(0.3, (0.5, 0.5, 0.5)), (0.7, (0.85, 0.85, 0.85))]), 'MULTIPLY')
    return shader.surface(color, 0.9, Sheen_Weight=0.5)


def add_wing(rig, anatomy, side, s, palette, material):
    # Flight feathers fanned off the hand (primaries) and forearm (secondaries),
    # tertials by the elbow and two rows of coverts on top, each feather
    # rigid on its bone; plus a leading edge over the bones.
    j = anatomy.joints
    chord = anatomy.wing[3]
    groups = [f"{bone}.{side}" for bone in WING_BONES]
    builder = MeshBuilder(attributes=("pstreak", "prand"), groups=("wind", *groups), colors=("pcol", "pedge"))
    rng = random.Random(7 + s)
    up = Vector((0, 0, 1))

    def feather(kind, index, bone, base, direction, length, width, layer, asymmetry=0.0, curve=0.06):
        color, edge, streak = palette(kind, index)
        weights = {g: (1.0 if g == f"{bone}.{side}" else 0.0) for g in groups}
        feather_outline(builder, base + up * (layer * 0.0012 * chord), direction, up, length, width, asymmetry=asymmetry * s,
                        curve=curve, pcol=color, pedge=edge, pstreak=streak, prand=rng.random(), **weights)

    wrist, tip, elbow, shoulder = j[f"wrist.{side}"], j[f"wingtip.{side}"], j[f"elbow.{side}"], j[f"shoulder.{side}"]
    back = Vector((0, 1, 0))
    out = (tip - wrist).normalized()
    for k in range(9):
        t = k / 8  # 0 at the wingtip, 1 at the wrist
        base = tip.lerp(wrist, 0.15 + 0.85 * t)
        direction = out.lerp(back, 0.15 + 0.6 * t ** 0.8).normalized()
        feather("primary", k, "hand", base, direction, chord * (1.0 - 0.15 * t), 0.28 * chord, 0, asymmetry=-0.4)
    for k in range(9):
        t = k / 8
        base = wrist.lerp(elbow, t)
        direction = (back + Vector((0.1 * s * (1 - t), 0, 0))).normalized()
        feather("secondary", k, "forearm", base, direction, chord * 0.78, 0.32 * chord, 1)
    for k in range(3):
        base = elbow.lerp(shoulder, 0.15 + 0.25 * k)
        feather("tertial", k, "arm", base, (back + Vector((-0.15 * s, 0, 0))).normalized(), chord * (0.65 - 0.1 * k), 0.26 * chord, 2)
    for k in range(14):
        t = k / 13
        base = (tip.lerp(wrist, 0.5) if t < 0.2 else wrist.lerp(shoulder, (t - 0.2) / 0.8)) + back * (0.05 * chord)
        bone = "hand" if t < 0.2 else "forearm" if t < 0.75 else "arm"
        feather("covert", k, bone, base, (back + Vector((0.2 * s, 0, 0))).normalized(), chord * 0.45, 0.2 * chord, 3)
        feather("lesser", k, bone, base - back * (0.08 * chord), (back + Vector((0.2 * s, 0, 0))).normalized(), chord * 0.27,
                0.17 * chord, 4)
    wing = builder.build(f"Wing.{side}", [material])
    wing.parent = rig
    wing.modifiers.new(name="Armature", type='ARMATURE').object = rig
    # A rounded leading edge over the bones.
    points = [shoulder, elbow, wrist, tip.lerp(wrist, 0.25)]
    radii = [0.17 * anatomy.radius, 0.1 * anatomy.radius, 0.07 * anatomy.radius, 0.03 * anatomy.radius]
    edge = add_tube(f"WingEdge.{side}", points, radii, edge_material(palette("lesser", 0)[0]), sides=8)
    bind(edge, rig, [b for b in anatomy.bones() if b[0] in groups])
    return wing, edge


def add_folded_wing(rig, bvh, anatomy, side, s, palette, material):
    # The same feathers closed up against the flank, as a wing at rest:
    # primaries innermost reaching back to the tail, secondaries and tertials
    # over them, coverts on top. (Flight feathers can't slide over each other
    # on rigid bones, so the open and folded wings are separate meshes.)
    j = anatomy.joints
    chord, r, length = anatomy.wing[3], anatomy.radius, anatomy.length
    shoulder = j[f"shoulder.{side}"]
    builder = MeshBuilder(attributes=("pstreak", "prand"), groups=("wind", "body"), colors=("pcol", "pedge"))
    rng = random.Random(11 + s)

    def feather(kind, index, y, z, droop, size, layer):
        color, edge, streak = palette(kind, index)
        location, normal = surface_point(bvh, Vector((s * r, shoulder.y + y * length, shoulder.z + z * r)))
        normal = (normal + Vector((0, 0, 0.3))).normalized()
        direction = Vector((0, 1, -droop))
        direction = (direction - normal * direction.dot(normal)).normalized()
        base = location + normal * (0.06 * r + layer * 0.025 * r)
        feather_outline(builder, base, direction, normal, chord * size, 0.22 * chord, curve=-0.04, pcol=color, pedge=edge,
                        pstreak=streak, prand=rng.random(), body=1.0)

    for k in range(9):
        feather("primary", k, 0.28 + 0.012 * k, -0.25 - 0.04 * k, 0.12 + 0.02 * k, 1.0 - 0.02 * k, k * 0.1)
    for k in range(9):
        feather("secondary", k, 0.1 + 0.025 * k, -0.15 - 0.05 * k, 0.25 + 0.02 * k, 0.78, 1 + k * 0.1)
    for k in range(3):
        feather("tertial", k, 0.18 + 0.05 * k, 0.15 - 0.08 * k, 0.1, 0.65 - 0.08 * k, 2.2 + k * 0.1)
    for k in range(10):
        feather("covert", k, 0.0 + 0.025 * k, -0.05 - 0.05 * k, 0.3, 0.45, 3.3 + k * 0.05)
        feather("lesser", k, -0.08 + 0.02 * k, 0.05 - 0.05 * k, 0.35, 0.27, 4.2 + k * 0.05)
    folded = builder.build(f"WingFolded.{side}", [material])
    folded.parent = rig
    folded.modifiers.new(name="Armature", type='ARMATURE').object = rig
    return folded


def edge_material(color):
    shader = Shader("WingEdge")
    fluff = shader.noise(shader.coords("Object"), 900.0, detail=4.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(fluff, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.0, 1.0, 1.0))]), 'MULTIPLY')
    return shader.surface(color, 0.7, Sheen_Weight=0.5)


def add_tail(rig, anatomy, palette, material):
    # Twelve rectrices fanned from the base of the tail, with coverts on top.
    j = anatomy.joints
    length, width = anatomy.tail
    builder = MeshBuilder(attributes=("pstreak", "prand"), groups=("wind", "tail"), colors=("pcol", "pedge"))
    rng = random.Random(3)
    base = j["tail"]
    axis = (j["tail.tip"] - base).normalized()
    up = Vector((0, 0, 1))
    for k in range(12):
        t = (k - 5.5) / 5.5
        direction = (axis + Vector((0.32 * t * width / length * 4, 0, 0))).normalized()
        color, edge, streak = palette("tail", k)
        layer = 5.5 - abs(k - 5.5)
        feather_outline(builder, base + Vector((0.18 * width * t, 0, 0.0008 * layer)), direction, up, length * (1 - 0.06 * abs(t)),
                        width / 3.5, curve=0.03, pcol=color, pedge=edge, pstreak=streak, prand=rng.random(), tail=1.0)
    for k in range(6):
        t = (k - 2.5) / 2.5
        color, edge, streak = palette("tail_covert", k)
        feather_outline(builder, base + Vector((0.15 * width * t, -0.1 * length, 0.006)), (axis + Vector((0.15 * t, 0, 0.1))).normalized(),
                        up, 0.45 * length, width / 3, curve=0.05, pcol=color, pedge=edge, pstreak=streak, prand=rng.random(), tail=1.0)
    tail = builder.build("Tail", [material])
    tail.parent = rig
    tail.modifiers.new(name="Armature", type='ARMATURE').object = rig
    return tail


def leg_material(color):
    # Scaly bare skin.
    shader = Shader("Leg")
    scales = shader.voronoi(shader.coords("Object"), 900.0, 'DISTANCE_TO_EDGE').outputs["Distance"]
    color = shader.mix(shader.math('LESS_THAN', scales, 0.08), color, tuple(0.5 * c for c in color))
    return shader.surface(color, 0.45, shader.bump(scales, 0.4, 0.0003))


def add_legs(rig, anatomy, color):
    # Slender tarsi and four clawed toes each: three forward, one back.
    j = anatomy.joints
    _, radius, toe = anatomy.legs
    material = leg_material(color)
    for side, s in SIDES:
        ankle, foot = j[f"ankle.{side}"], j[f"foot.{side}"]
        rigid(add_tube(f"Tarsus.{side}", [ankle + Vector((0, 0, 0.6 * radius)), ankle.lerp(foot, 0.5), foot],
                       [1.2 * radius, radius, 0.9 * radius], material, sides=8), rig, f"tarsus.{side}")
        for k, (angle, reach) in enumerate(((-0.45, 0.85), (0.0, 1.0), (0.45, 0.85), (math.pi, 0.6))):
            direction = Vector((math.sin(angle) * s, -math.cos(angle), 0))
            points = [foot]
            for step in range(1, 4):
                points.append(foot + direction * (toe * reach * step / 3) + Vector((0, 0, -0.5 * radius * (step == 3))))
            claw = points[-1] + direction * (0.25 * toe) + Vector((0, 0, -0.6 * radius))
            rigid(add_tube(f"Toe.{side}.{k}", points + [claw], [0.8 * radius, 0.7 * radius, 0.6 * radius, 0.45 * radius, 0.05 * radius],
                           material, sides=6), rig, f"toes.{side}")


def beak_material(color):
    shader = Shader("Beak")
    grain = shader.noise(shader.coords("Object", (1.0, 30.0, 1.0)), 400.0, detail=3.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(grain, [(0.3, (0.8, 0.8, 0.8)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    return shader.surface(color, 0.3, shader.bump(grain, 0.2, 0.0005), Coat_Weight=0.3)


def add_head(rig, bvh, anatomy, beak_color, iris=(0.05, 0.03, 0.02)):
    # Beak (upper and lower mandibles) and eyes. Returns the spots plumage
    # should keep clear of.
    j = anatomy.joints
    base_radius = anatomy.beak[1]
    material = beak_material(beak_color)
    base, tip = j["beak"], j["tip"]
    upper = [base + Vector((0, 0, 0.3 * base_radius)), base.lerp(tip, 0.5) + Vector((0, 0, 0.15 * base_radius)), tip]
    rigid(add_tube("Beak.Upper", upper, [base_radius, 0.55 * base_radius, 0.04 * base_radius], material, sides=12), rig, "head")
    lower = [base - Vector((0, 0, 0.35 * base_radius)), base.lerp(tip, 0.45) - Vector((0, 0, 0.3 * base_radius)),
             tip.lerp(base, 0.1) - Vector((0, 0, 0.1 * base_radius))]
    rigid(add_tube("Beak.Lower", lower, [0.8 * base_radius, 0.4 * base_radius, 0.04 * base_radius], material, sides=12), rig, "head")
    features = [(base, 1.3 * base_radius)]
    r = anatomy.head_radius
    eye = eye_material(iris)
    for side, s in SIDES:
        location, normal = surface_point(bvh, j["head"] + Vector((0.8 * r * s, -0.35 * r, 0.15 * r)))
        size = 0.22 * r
        centre = location - normal * (0.3 * size)
        rigid(add_sphere(f"Eye.{side}", centre, size, eye), rig, "head")
        features.append((centre, 1.25 * size))
    return features


def build_bird(name, anatomy, coat, palette, beak_color, leg_color, iris=(0.05, 0.03, 0.02), sheen=0.3, film=0.0):
    # The rigged, feathered bird. Returns the rig, the plumage's "Fly" input,
    # the open and the folded wings, and the meshes of flight feathers (for the wind).
    bones = anatomy.bones()
    rig = add_armature(f"{name}Rig", bones)
    body = skin_mesh(name, *anatomy.skeleton())
    main = bind(body, rig, [b for b in bones if b[0] in ("body", "neck", "head", "tail")])
    bvh = BVHTree.FromPolygons([v.co for v in body.data.vertices], [p.vertices for p in body.data.polygons])
    material = plumage_material(sheen, film)
    features = add_head(rig, bvh, anatomy, beak_color, iris)
    fly = add_plumage(body, main, coat, features, material)
    opened = [part for side, s in SIDES for part in add_wing(rig, anatomy, side, s, palette, material)]
    folded = [add_folded_wing(rig, bvh, anatomy, side, s, palette, material) for side, s in SIDES]
    tail = add_tail(rig, anatomy, palette, material)
    add_legs(rig, anatomy, leg_color)
    return rig, fly, opened, folded, [part for part in opened if part.name.startswith("Wing.")] + folded + [tail]


def walk_pose(p):
    # A stately walk: legs alternating, the head bobbing back and forth, the
    # tail flicking.
    turns = {
        "body": [("Y", 0.04 * math.sin(p))],
        "neck": [("X", 0.12 * math.sin(2 * p))],
        "head": [("X", -0.1 * math.sin(2 * p))],
        "tail": [("X", 0.12 * max(0.0, math.sin(2 * p)) ** 4)],
    }
    for side, s in SIDES:
        phase = p + (0 if s > 0 else math.pi)
        raised = max(0.0, math.sin(phase))
        turns[f"thigh.{side}"] = [("X", 0.3 * math.cos(phase))]
        turns[f"tarsus.{side}"] = [("X", 0.9 * raised)]
        turns[f"toes.{side}"] = [("X", -0.8 * raised)]
    return turns, 0.004 * math.sin(2 * p)


def flight_pose(p, beat):
    # Wingbeats (beat is the stroke amplitude in radians) with the legs
    # tucked up and the body level.
    turns = {
        "body": [("X", -0.12 + 0.05 * math.sin(p + 1.5))],
        "neck": [("X", -0.2)],
        "head": [("X", 0.25)],
        "tail": [("X", 0.05 * math.sin(p))],
    }
    for side, s in SIDES:
        down = math.sin(p)
        turns[f"arm.{side}"] = [("X", -0.12 * math.cos(p)), ("Y", s * (0.1 + beat * down))]
        turns[f"forearm.{side}"] = [("Y", s * 0.35 * beat * math.sin(p - 0.6)), ("Z", s * 0.25 * max(0.0, -down))]
        turns[f"hand.{side}"] = [("Y", s * 0.45 * beat * math.sin(p - 1.1)), ("Z", -s * 0.35 * max(0.0, -down))]
        turns[f"thigh.{side}"] = [("X", 0.7)]
        turns[f"tarsus.{side}"] = [("X", 1.6)]
        turns[f"toes.{side}"] = [("X", -1.2)]
    return turns, 0.0


def animate(rig, fly, opened, folded, flappers, walk_speed, walk_rate, fly_speed, flap_rate, beat, altitude, camera_distance,
            camera_height, camera_lift, lens=50, fstop=4.0, camera_sweep=(200, 165), glide=0.0):
    # Walks for the first half of the timeline, then takes off and flies away,
    # climbing to altitude. walk_rate is strides (two steps) per second,
    # flap_rate wingbeats per second; glide (0..1) is how much of the time it
    # glides once airborne. fly (the plumage's "Fly" input) and the flutter of
    # the flight feathers follow along, and the folded wings give way to the
    # open ones at takeoff; the camera rides alongside, rising camera_lift
    # above (or sinking below) its walking height during the climb.
    scene = bpy.context.scene
    takeoff = (scene.frame_start + scene.frame_end) // 2
    mover = bpy.data.objects.new(name="Mover", object_data=None)
    bpy.context.collection.objects.link(mover)
    rig.parent = mover
    camera = add_follow_camera(mover, rig, "body", lens, fstop)
    rest = rest_frames(rig)
    flutter = [m for obj in flappers for m in obj.modifiers if m.type == 'DISPLACE']
    calm = [m.strength for m in flutter]
    distance, walk_phase, flap_phase = 0.0, 0.0, 0.0
    previous = scene.frame_start
    # Every frame: wingbeats are too quick for keyframes further apart.
    for frame_number in timeline_frames(step=1):
        dt = (frame_number - previous) / FPS
        previous = frame_number
        t = (frame_number - takeoff) / FPS
        flight = smootherstep(t / 0.35 + 0.5)
        climb = smootherstep(t / 2.5)
        distance += lerp(walk_speed, fly_speed, smootherstep(t / 1.5)) * dt
        walk_phase += 2 * math.pi * walk_rate * dt
        gliding = glide * smootherstep((math.sin(1.3 * t) - 0.3) / 0.4) if t > 1.5 else 0.0
        flap_phase += 2 * math.pi * flap_rate * dt * (1 - gliding)
        walk_turns, bob = walk_pose(walk_phase)
        fly_turns, _ = flight_pose(flap_phase, beat * (1 - gliding))
        for bone in rig.pose.bones:
            bone_rest = rest[bone.name]
            flying = turn(bone_rest, fly_turns.get(bone.name, ()))
            if bone.name.split(".")[0] in WING_BONES:
                # Hidden until takeoff, so they can beat from the start.
                bone.rotation_quaternion = flying
            else:
                bone.rotation_quaternion = turn(bone_rest, walk_turns.get(bone.name, ())).slerp(flying, flight)
            bone.keyframe_insert("rotation_quaternion", frame=frame_number)

        mover.location = (0, -distance, altitude * climb)
        mover.keyframe_insert("location", frame=frame_number)
        rig.location = (0, 0, bob * (1 - flight))
        rig.keyframe_insert("location", frame=frame_number)
        fly.value = flight
        fly.keyframe_insert("value", frame=frame_number)
        for modifier, strength in zip(flutter, calm):
            modifier.strength = strength * (1 + 1.5 * flight)
            modifier.keyframe_insert("strength", frame=frame_number)

        progress = (frame_number - scene.frame_start) / (scene.frame_end - scene.frame_start)
        angle = math.radians(lerp(*camera_sweep, progress))
        camera.location = (camera_distance * math.cos(angle), camera_distance * math.sin(angle),
                           camera_height + camera_lift * climb)
        camera.keyframe_insert("location", frame=frame_number)
    for obj in opened + folded:
        for frame_number, airborne in ((scene.frame_start, False), (takeoff, True)):
            obj.hide_render = obj.hide_viewport = airborne == (obj in folded)
            obj.keyframe_insert("hide_render", frame=frame_number)
            obj.keyframe_insert("hide_viewport", frame=frame_number)
    return distance


def add_feather_wind(feathers, size):
    # Gusts and a quick flutter lifting the free ends of the flight feathers.
    gusts = add_mover("FeatherGusts", (0.1, 0.0, 0.03))
    flutter = add_mover("FeatherFlutter", (0.02, 0.01, 0.06))
    for obj in feathers:
        add_displace(obj, gusts, size=2.0, strength=0.25 * size, direction='Z', mid_level=0.3)
        add_displace(obj, flutter, size=0.05, strength=0.12 * size, direction='Z')
