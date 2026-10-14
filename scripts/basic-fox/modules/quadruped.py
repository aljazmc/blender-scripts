import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from modules.nature import FPS, Shader, MeshBuilder, Nodes, modifier_inputs
from modules.body import (SIDES, lerp, smootherstep, add_armature, bind, rigid, surface_point, add_sphere,
                          add_tube, eye_material, turn, skin_mesh, add_follow_camera, rest_frames,
                          timeline_frames)

LEGS = ("F", "B")


class Anatomy:
    # Joint positions for a four-legged animal facing -Y, standing on z = 0,
    # worked out from a few proportions:
    #   length: shoulder to hip; height: at the withers; width: half the gap between the legs
    #   chest, waist, hips: body radii; neck: (length, angle up from level, base radius, top radius)
    #   head: (skull length, radius); snout: (length, radius, droop)
    #   legs: (upper radius, lower radius, paw radius); tail: (length, radius, angle down from level)
    #   front, hind: joint heights as fractions of height (elbow, wrist) and (knee, hock)

    def __init__(self, length, height, width, chest, waist, hips, neck, head, snout, legs, tail,
                 front=(0.55, 0.17), hind=(0.58, 0.28)):
        self.length, self.height, self.width = length, height, width
        self.chest, self.waist, self.hips = chest, waist, hips
        self.legs = legs
        self.joints = {}
        half = length / 2
        j = self.joints
        j["waist"] = Vector((0, 0, height - 1.1 * waist))
        j["chest"] = Vector((0, -half, height - chest))
        j["hips"] = Vector((0, half, 0.97 * height - hips))
        j["brisket"] = j["chest"] + Vector((0, -0.55 * chest, 0.05 * chest))
        neck_length, neck_angle, self.neck_radii = neck[0], math.radians(neck[1]), neck[2:]
        j["neck"] = j["chest"] + Vector((0, -0.45 * chest, 0.55 * chest))
        j["skull"] = j["neck"] + Vector((0, -math.cos(neck_angle), math.sin(neck_angle))) * neck_length
        skull_length, self.head_radius = head
        j["muzzle"] = j["skull"] + Vector((0, -skull_length, -0.25 * skull_length))
        snout_length, self.snout_radius, droop = snout
        j["nose"] = j["muzzle"] + Vector((0, -snout_length, -droop))
        tail_length, self.tail_radius, tail_angle = tail
        tail_dir = Vector((0, math.cos(math.radians(tail_angle)), -math.sin(math.radians(tail_angle))))
        for k in range(4):
            j[f"tail.{k}"] = j["hips"] + Vector((0, 0.85 * hips, 0.35 * hips)) + tail_dir * (tail_length * k / 3)
        # Each tail joint droops a little more than the last.
        for k in range(2, 4):
            j[f"tail.{k}"] += Vector((0, 0, -0.06 * tail_length * (k - 1)))
        for side, s in SIDES:
            x = width * s
            j[f"upper.F.{side}"] = Vector((x, -half, 0.8 * height))
            j[f"lower.F.{side}"] = Vector((x, -half + 0.07 * height, front[0] * height))
            j[f"foot.F.{side}"] = Vector((x, -half, front[1] * height))
            j[f"toe.F.{side}"] = Vector((x, -half - 0.06 * height, legs[2]))
            j[f"upper.B.{side}"] = Vector((x, half, 0.82 * height))
            j[f"lower.B.{side}"] = Vector((x, half - 0.13 * height, hind[0] * height))
            j[f"foot.B.{side}"] = Vector((x, half + 0.12 * height, hind[1] * height))
            j[f"toe.B.{side}"] = Vector((x, half + 0.07 * height, legs[2]))

    def bones(self):
        # (name, head, tail, parent, radius at head, radius at tail); parents first.
        j = self.joints
        upper, lower, paw = self.legs
        bones = [
            ("chest", j["waist"], j["chest"], None, self.waist, self.chest),
            ("hips", j["waist"], j["hips"], None, self.waist, self.hips),
            ("neck", j["neck"], j["skull"], "chest", self.neck_radii[0], self.neck_radii[1]),
            ("head", j["skull"], j["muzzle"], "neck", self.head_radius, 0.6 * self.head_radius),
            ("snout", j["muzzle"], j["nose"], "head", 0.6 * self.head_radius, self.snout_radius),
            ("tail.1", j["tail.0"], j["tail.1"], "hips", self.tail_radius, 0.9 * self.tail_radius),
            ("tail.2", j["tail.1"], j["tail.2"], "tail.1", 0.9 * self.tail_radius, 0.7 * self.tail_radius),
            ("tail.3", j["tail.2"], j["tail.3"], "tail.2", 0.7 * self.tail_radius, 0.4 * self.tail_radius),
        ]
        for side, _ in SIDES:
            for leg, body in (("F", "chest"), ("B", "hips")):
                thick = 1.25 * upper if leg == "B" else upper
                bones += [
                    (f"upper.{leg}.{side}", j[f"upper.{leg}.{side}"], j[f"lower.{leg}.{side}"], body, thick, 0.75 * thick),
                    (f"lower.{leg}.{side}", j[f"lower.{leg}.{side}"], j[f"foot.{leg}.{side}"], f"upper.{leg}.{side}", 0.75 * thick, lower),
                    (f"foot.{leg}.{side}", j[f"foot.{leg}.{side}"], j[f"toe.{leg}.{side}"], f"lower.{leg}.{side}", lower, paw),
                ]
        return bones

    def skeleton(self):
        # The graph the Skin modifier wraps in flesh: (joint, radius) nodes and edges.
        j = self.joints
        upper, lower, paw = self.legs
        nodes = [
            ("hips", self.hips), ("waist", self.waist), ("chest", self.chest),
            ("brisket", 0.75 * self.chest), ("neck", self.neck_radii[0]), ("skull", self.head_radius),
            ("muzzle", 0.6 * self.head_radius), ("nose", self.snout_radius),
            ("tail.0", self.tail_radius), ("tail.1", 0.9 * self.tail_radius),
            ("tail.2", 0.7 * self.tail_radius), ("tail.3", 0.35 * self.tail_radius),
        ]
        edges = [("hips", "waist"), ("waist", "chest"), ("chest", "brisket"), ("brisket", "neck"),
                 ("neck", "skull"), ("skull", "muzzle"), ("muzzle", "nose"), ("hips", "tail.0"),
                 ("tail.0", "tail.1"), ("tail.1", "tail.2"), ("tail.2", "tail.3")]
        for side, _ in SIDES:
            for leg, body in (("F", "chest"), ("B", "hips")):
                thick = 1.25 * upper if leg == "B" else upper
                nodes += [(f"upper.{leg}.{side}", thick), (f"lower.{leg}.{side}", 0.7 * thick),
                          (f"foot.{leg}.{side}", lower), (f"toe.{leg}.{side}", paw)]
                edges += [(body, f"upper.{leg}.{side}"), (f"upper.{leg}.{side}", f"lower.{leg}.{side}"),
                          (f"lower.{leg}.{side}", f"foot.{leg}.{side}"), (f"foot.{leg}.{side}", f"toe.{leg}.{side}")]
        return [(j[name], radius) for name, radius in nodes], [([n for n, _ in nodes].index(a), [n for n, _ in nodes].index(b)) for a, b in edges]


def build_body(anatomy, name):
    points, edges = anatomy.skeleton()
    return skin_mesh(name, points, edges)


def add_ear(name, base, normal, forward, length, width, material):
    # A cupped, pointed ear: a fan of quads opening towards forward.
    normal, forward = Vector(normal).normalized(), Vector(forward).normalized()
    side = forward.cross(normal).normalized()
    builder = MeshBuilder()
    rows, cols = 5, 6
    verts = []
    for r in range(rows + 1):
        t = r / rows
        half = 0.5 * width * (1 - t) ** 0.9
        for c in range(cols + 1):
            a = (c / cols - 0.5) * math.pi
            # Cupped: the sides curl forwards.
            verts.append(tuple(base + normal * (length * t) + side * (math.sin(a) * half)
                               - forward * (0.5 * half * math.cos(a) - 0.25 * half)))
    faces = []
    for r in range(rows):
        for c in range(cols):
            a = r * (cols + 1) + c
            faces.append([a, a + 1, a + cols + 2, a + cols + 1])
    builder.add(verts, faces)
    return builder.build(name, [material])


def fur_material(tip_color):
    # Coloured from the skin under each strand, darker at the root, with
    # dark-tipped guard hairs where "fur_tip" says so.
    shader = Shader("Fur")
    color = shader.node("ShaderNodeAttribute", attribute_name="fur_col").outputs["Color"]
    tip = shader.node("ShaderNodeAttribute", attribute_name="fur_tip").outputs["Fac"]
    hair = shader.node("ShaderNodeHairInfo")
    intercept = hair.outputs["Intercept"]
    root = shader.math('POWER', intercept, 0.5)
    color = shader.mix(1.0, color, shader.mix(root, (0.35, 0.35, 0.35), (1.0, 1.0, 1.0)), 'MULTIPLY')
    band = shader.math('MULTIPLY', tip, shader.node("ShaderNodeMapRange", {"Value": intercept, 1: 0.7, 2: 0.9}).outputs[0])
    color = shader.mix(band, color, tip_color)
    variation = shader.ramp(hair.outputs["Random"], [(0.0, (0.75, 0.75, 0.75)), (1.0, (1.15, 1.15, 1.15))])
    color = shader.mix(1.0, color, variation, 'MULTIPLY')
    return shader.surface(color, 0.5, Specular_IOR_Level=0.35)


def skin_material():
    # The hide under the fur, so gaps between strands show the coat colour.
    shader = Shader("Hide")
    color = shader.node("ShaderNodeAttribute", attribute_name="fur_col").outputs["Color"]
    noise = shader.noise(shader.coords("Object"), 400.0, detail=4.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(noise, [(0.3, (0.35, 0.35, 0.35)), (0.7, (0.7, 0.7, 0.7))]), 'MULTIPLY')
    return shader.surface(color, 0.8, shader.bump(noise, 0.3, 0.002))


def fur_nodes(body, material):
    # Geometry nodes growing strands over the posed body: combed back and
    # down, blown about by gusting wind and streaming back as the animal runs.
    # (Only a Curves object renders strands, so they live on one of their own.)
    tree = Nodes("Fur")
    tree.socket("Density", 'NodeSocketFloat', default=50000.0)
    tree.socket("Length", 'NodeSocketFloat', default=1.0)
    tree.socket("Radius", 'NodeSocketFloat', default=0.0006)
    tree.socket("Wind", 'NodeSocketVector', default=(1.0, 0.0, 0.0))
    tree.socket("Run", 'NodeSocketFloat', default=0.0)
    tree.socket("Geometry", 'NodeSocketGeometry', in_out='OUTPUT')
    node, math_node, vector, attribute = tree.node, tree.math, tree.vector, tree.attribute

    source = node("NodeGroupInput").outputs
    out = node("NodeGroupOutput")
    skin = node("GeometryNodeObjectInfo", {"Object": body}, transform_space='RELATIVE').outputs["Geometry"]
    has_fur = math_node('GREATER_THAN', attribute("fur_len"), 0.001)
    points = node("GeometryNodeDistributePointsOnFaces", {"Mesh": skin, "Selection": has_fur,
                                                          "Density": source["Density"], "Seed": 3})
    # Combed backwards and down, with a little scatter.
    scatter = node("FunctionNodeRandomValue", {0: (-0.35, -0.35, -0.35), 1: (0.35, 0.35, 0.35)}, data_type='FLOAT_VECTOR').outputs[0]
    comb = vector('ADD', vector('ADD', points.outputs["Normal"], (0.0, 0.9, -0.5)), scatter)
    rotation = node("FunctionNodeAlignRotationToVector", {"Vector": comb}, axis='Z').outputs[0]
    spread = node("FunctionNodeRandomValue", {"Min": 0.6, "Max": 1.2}).outputs[0]
    length = math_node('MULTIPLY', math_node('MULTIPLY', attribute("fur_len"), spread), source["Length"])
    strand = node("GeometryNodeCurvePrimitiveLine", {"End": (0.0, 0.0, 1.0)})
    strand = node("GeometryNodeResampleCurve", {"Curve": strand.outputs[0], "Count": 5})
    planted = node("GeometryNodeInstanceOnPoints", {"Points": points.outputs["Points"], "Instance": strand.outputs[0],
                                                    "Rotation": rotation, "Scale": length})
    realized = node("GeometryNodeRealizeInstances", {"Geometry": planted.outputs[0]})
    # The further along the strand, the more it bends.
    along = node("GeometryNodeSplineParameter").outputs["Factor"]
    reach = math_node('MULTIPLY', attribute("fur_len"), source["Length"])
    seconds = node("GeometryNodeInputSceneTime").outputs["Seconds"]
    position = node("GeometryNodeInputPosition").outputs[0]
    gust = node("ShaderNodeTexNoise", {"Vector": position, "W": math_node('MULTIPLY', seconds, 0.8), "Scale": 0.8, "Detail": 1.0},
                noise_dimensions='4D').outputs["Factor"]
    gust = math_node('MAXIMUM', math_node('MULTIPLY', math_node('SUBTRACT', gust, 0.35), 3.0), 0.0)
    flutter = node("ShaderNodeTexNoise", {"Vector": position, "W": math_node('MULTIPLY', seconds, 5.0), "Scale": 6.0, "Detail": 1.0},
                   noise_dimensions='4D').outputs["Color"]
    flutter = vector('SUBTRACT', flutter, (0.5, 0.5, 0.5))
    wind = vector('SCALE', source["Wind"], scale=gust)
    stream = vector('SCALE', (0.0, 1.4, 0.15), scale=source["Run"])
    shake = vector('SCALE', flutter, scale=math_node('ADD', 0.8, math_node('MULTIPLY', source["Run"], 1.5)))
    push = vector('ADD', vector('ADD', wind, stream), shake)
    bend = math_node('MULTIPLY', math_node('POWER', along, 1.5), reach)
    offset = vector('ADD', vector('SCALE', push, scale=bend),
                    vector('SCALE', (0.0, 0.0, -0.3), scale=math_node('MULTIPLY', math_node('POWER', along, 2.0), reach)))
    blown = node("GeometryNodeSetPosition", {"Geometry": realized.outputs[0], "Offset": offset})
    radius = math_node('MULTIPLY', source["Radius"], math_node('SUBTRACT', 1.0, math_node('MULTIPLY', along, 0.85)))
    thinned = node("GeometryNodeSetCurveRadius", {"Curve": blown.outputs[0], "Radius": radius})
    dressed = node("GeometryNodeSetMaterial", {"Geometry": thinned.outputs[0], "Material": material})
    tree.set(out.inputs[0], dressed.outputs[0])
    return tree.group


def add_fur(body, main_bone, coat, features, tip_color, density, radius, wind):
    # coat(position, normal, bone) -> (colour, fur length, dark tip 0..1) for
    # each vertex; strands stay clear of the features (eyes, nose).
    mesh = body.data
    colors, lengths, tips = [], [], []
    for vertex, bone in zip(mesh.vertices, main_bone):
        color, length, tip = coat(vertex.co, vertex.normal, bone)
        for centre, clearance in features:
            length *= smootherstep(((vertex.co - centre).length - clearance) / clearance)
        colors += [*color, 1.0]
        lengths.append(length)
        tips.append(tip)
    mesh.color_attributes.new(name="fur_col", type='FLOAT_COLOR', domain='POINT').data.foreach_set("color", colors)
    mesh.attributes.new(name="fur_len", type='FLOAT', domain='POINT').data.foreach_set("value", lengths)
    mesh.attributes.new(name="fur_tip", type='FLOAT', domain='POINT').data.foreach_set("value", tips)
    mesh.materials.append(skin_material())
    material = fur_material(tip_color)
    fur = bpy.data.objects.new(name="Fur", object_data=bpy.data.hair_curves.new(name="Fur"))
    fur.data.materials.append(material)
    bpy.context.collection.objects.link(fur)
    modifier = fur.modifiers.new(name="Fur", type='NODES')
    modifier.node_group = fur_nodes(body, material)
    inputs = modifier_inputs(modifier)
    inputs["Density"].value = density
    inputs["Radius"].value = radius
    inputs["Wind"].value = wind
    bpy.context.scene.render.hair_type = 'STRIP'
    return inputs["Run"]


def build_animal(name, anatomy, coat, tip_color, density=60000.0, radius=0.0006, wind=(0.8, 0.0, 0.1)):
    # The rigged, furred body. Returns the rig, a BVH of the body
    # surface for placing features, and a function that adds the fur once the
    # features are known.
    bones = anatomy.bones()
    rig = add_armature(f"{name}Rig", bones)
    body = build_body(anatomy, name)
    main = bind(body, rig, bones)
    mesh = body.data
    bvh = BVHTree.FromPolygons([v.co for v in mesh.vertices], [p.vertices for p in mesh.polygons])

    def grow_fur(features):
        return add_fur(body, main, coat, features, tip_color, density, radius, wind)

    return rig, bvh, grow_fur


def nose_material():
    shader = Shader("Nose")
    bumps = shader.voronoi(shader.coords("Object"), 900.0).outputs["Distance"]
    return shader.surface((0.015, 0.012, 0.012), 0.3, shader.bump(bumps, 0.5, 0.0005))


def add_face(rig, bvh, anatomy, ear_material, ear_size=(0.1, 0.06), ear_spread=0.6, ear_tilt=0.2, eye_size=0.012):
    # Eyes, nose and ears, placed on the head's surface. Returns the spots fur
    # should keep clear of.
    j = anatomy.joints
    skull, muzzle, nose = j["skull"], j["muzzle"], j["nose"]
    r = anatomy.head_radius
    features = []
    eye = eye_material()
    for side, s in SIDES:
        guess = skull.lerp(muzzle, 0.75) + Vector((0.75 * r * s, 0, 0.45 * r))
        location, normal = surface_point(bvh, guess)
        centre = location - normal * (0.35 * eye_size)
        rigid(add_sphere(f"Eye.{side}", centre, eye_size, eye), rig, "head")
        features.append((centre, 1.6 * eye_size))
        base, normal = surface_point(bvh, skull + Vector((0.55 * r * s, 0.15 * r, 0.9 * r)))
        up = Vector((s * math.sin(ear_spread), ear_tilt, math.cos(ear_spread))).normalized()
        ear = add_ear(f"Ear.{side}", base - normal * 0.005, up, Vector((0.25 * s, -1, 0)), ear_size[0], ear_size[1], ear_material)
        rigid(ear, rig, "head")
    location, normal = surface_point(bvh, nose + Vector((0, -0.02, 0.01)))
    rigid(add_sphere("Nose", location - normal * 0.006, 0.8 * anatomy.snout_radius, nose_material(), scale=(1.2, 0.9, 0.75)), rig, "snout")
    features.append((location, 1.4 * anatomy.snout_radius))
    return features


def ear_material(outside, inside):
    shader = Shader("Ear")
    backfacing = shader.node("ShaderNodeNewGeometry").outputs["Backfacing"]
    noise = shader.noise(shader.coords("Object"), 600.0, detail=4.0).outputs["Fac"]
    color = shader.mix(backfacing, outside, inside)
    color = shader.mix(1.0, color, shader.ramp(noise, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    return shader.surface(color, 0.7, shader.bump(noise, 0.4, 0.001), translucency=0.15)


def leg_turns(leg, side, phase, swing, lift):
    # The upper leg swings back and forth; the joints below fold while the
    # leg is carried forward.
    raised = max(0.0, -math.cos(phase))
    name = f"{leg}.{side}"
    if leg == "F":
        return {f"upper.{name}": [("X", swing * math.sin(phase))],
                f"lower.{name}": [("X", 0.5 * lift * raised)],
                f"foot.{name}": [("X", 1.1 * lift * raised)]}
    return {f"upper.{name}": [("X", swing * math.sin(phase) - 0.3 * lift * raised)],
            f"lower.{name}": [("X", 0.7 * lift * raised)],
            f"foot.{name}": [("X", -0.9 * lift * raised)]}


WALK_PHASES = {"B.L": 0.0, "F.L": 0.5 * math.pi, "B.R": math.pi, "F.R": 1.5 * math.pi}
GALLOP_PHASES = {"B.L": 0.0, "B.R": 0.35, "F.L": math.pi - 0.2, "F.R": math.pi + 0.2}


def walk_pose(p, swing=0.35, lift=0.8):
    # A four-beat walk: hind left, fore left, hind right, fore right.
    turns = {
        "chest": [("Y", 0.03 * math.sin(p)), ("Z", 0.03 * math.sin(p))],
        "hips": [("Y", -0.03 * math.sin(p)), ("Z", 0.03 * math.sin(p))],
        "neck": [("X", 0.05 * math.sin(2 * p))],
        "head": [("X", -0.05 * math.sin(2 * p))],
        "tail.1": [("X", -0.15), ("Z", 0.12 * math.sin(p))],
        "tail.2": [("Z", 0.15 * math.sin(p - 0.7))],
        "tail.3": [("Z", 0.2 * math.sin(p - 1.4))],
    }
    for name, phase in WALK_PHASES.items():
        leg, side = name.split(".")
        turns.update(leg_turns(leg, side, p + phase, swing, lift))
    return turns, 0.012 * math.sin(2 * p)


def gallop_pose(p, swing=0.75, lift=1.2):
    # A rotary gallop: the back flexes to bunch the legs, then stretches out.
    flex = math.sin(p + 0.3)
    turns = {
        "chest": [("X", 0.12 * flex)],
        "hips": [("X", -0.14 * flex)],
        "neck": [("X", 0.25 + 0.12 * math.sin(p + 1.0))],
        "head": [("X", -0.2 - 0.08 * math.sin(p + 1.0))],
        "tail.1": [("X", -0.35 + 0.1 * math.sin(p))],
        "tail.2": [("X", 0.08 * math.sin(p - 0.8))],
        "tail.3": [("X", 0.1 * math.sin(p - 1.6))],
    }
    for name, phase in GALLOP_PHASES.items():
        leg, side = name.split(".")
        turns.update(leg_turns(leg, side, p + phase, swing, lift))
    return turns, 0.06 * math.sin(p + 1.2)


def animate(rig, fur, walk_speed, run_speed, walk_rate, run_rate, camera_distance, camera_height, lens=50, fstop=4.0,
            camera_sweep=(205, 160), walk=walk_pose, gallop=gallop_pose):
    # Walks for the first half of the timeline and gallops for the second,
    # blending over about a second. walk_rate and run_rate are strides per
    # second. The camera rides alongside, swinging round through camera_sweep
    # (degrees; 180 is the animal's right side), and fur (the fur's "Run"
    # input) follows the gait.
    scene = bpy.context.scene
    switch = (scene.frame_start + scene.frame_end) // 2
    mover = bpy.data.objects.new(name="Mover", object_data=None)
    bpy.context.collection.objects.link(mover)
    rig.parent = mover
    camera = add_follow_camera(mover, rig, "chest", lens, fstop)
    rest = rest_frames(rig)
    distance, phase = 0.0, 0.0
    previous = scene.frame_start
    for frame in timeline_frames():
        dt = (frame - previous) / FPS
        previous = frame
        run = smootherstep((frame - switch) / FPS + 0.5)
        distance += lerp(walk_speed, run_speed, run) * dt
        # Both gaits share one cycle, sped up smoothly, so the blend never jumps.
        phase += 2 * math.pi * lerp(walk_rate, run_rate, run) * dt
        walk_turns, walk_bob = walk(phase)
        run_turns, run_bob = gallop(phase)
        for bone in rig.pose.bones:
            bone_rest = rest[bone.name]
            bone.rotation_quaternion = turn(bone_rest, walk_turns.get(bone.name, ())).slerp(
                turn(bone_rest, run_turns.get(bone.name, ())), run)
            bone.keyframe_insert("rotation_quaternion", frame=frame)

        mover.location = (0, -distance, 0)
        mover.keyframe_insert("location", frame=frame)
        rig.location = (0, 0, lerp(walk_bob, run_bob, run))
        rig.keyframe_insert("location", frame=frame)
        fur.value = run
        fur.keyframe_insert("value", frame=frame)

        progress = (frame - scene.frame_start) / (scene.frame_end - scene.frame_start)
        angle = math.radians(lerp(*camera_sweep, progress))
        camera.location = (camera_distance * math.cos(angle), camera_distance * math.sin(angle) - 0.3 * run, camera_height)
        camera.keyframe_insert("location", frame=frame)
    return distance


def hoof_material():
    shader = Shader("Hoof")
    streaks = shader.noise(shader.coords("Object", (40.0, 40.0, 4.0)), 20.0, detail=3.0).outputs["Fac"]
    color = shader.ramp(streaks, [(0.3, (0.012, 0.01, 0.008)), (0.7, (0.05, 0.04, 0.03))])
    return shader.surface(color, 0.35, shader.bump(streaks, 0.3, 0.001))


def add_hooves(rig, anatomy):
    # Split hooves at the bottom of each foot. Returns the spots fur should
    # keep clear of.
    material = hoof_material()
    features = []
    radius = anatomy.legs[2]
    for side, _ in SIDES:
        for leg in LEGS:
            toe = anatomy.joints[f"toe.{leg}.{side}"]
            for split in (-1, 1):
                points = [toe + Vector((0.4 * radius * split, 0.1 * radius, -radius)),
                          toe + Vector((0.4 * radius * split, -0.3 * radius, 0.4 * radius)),
                          toe + Vector((0.35 * radius * split, -0.5 * radius, 1.2 * radius))]
                hoof = add_tube(f"Hoof.{leg}.{side}.{split}", points, [0.6 * radius, 0.55 * radius, 0.35 * radius], material)
                rigid(hoof, rig, f"foot.{leg}.{side}")
            features.append((toe, 1.6 * radius))
    return features
