import math

import bpy
from mathutils import Vector

from modules.nature import FPS, Shader
from modules.body import (SIDES, smootherstep, add_armature, bind, rigid, add_sphere, add_tube, eye_material, turn,
                          skin_mesh, rest_frames, timeline_frames)


class Anatomy:
    # Joint positions for a person facing -Y, standing on z = 0, scaled from
    # a 1.8 m template; build widens the shoulders and thickens the limbs.

    def __init__(self, height=1.8, build=1.0):
        k = height / 1.8
        self.k, self.build = k, build
        w = build
        j = self.joints = {}

        def put(name, x, y, z):
            j[name] = Vector((x, y, z)) * k

        put("pelvis", 0, 0.0, 0.96)
        put("belly", 0, -0.01, 1.1)
        put("chest", 0, 0.0, 1.3)
        put("collar", 0, 0.01, 1.43)
        put("neck", 0, 0.015, 1.5)
        put("skull", 0, 0.0, 1.6)
        put("crown", 0, 0.0, 1.8)
        for side, s in SIDES:
            put(f"clavicle.{side}", 0.04 * s, 0.01, 1.44)
            put(f"shoulder.{side}", 0.19 * w * s, 0.015, 1.42)
            put(f"elbow.{side}", 0.22 * w * s, 0.04, 1.14)
            put(f"wrist.{side}", 0.235 * w * s, 0.01, 0.89)
            put(f"knuckles.{side}", 0.24 * w * s, -0.0, 0.81)
            put(f"hip.{side}", 0.095 * s, 0.0, 0.92)
            put(f"knee.{side}", 0.1 * s, -0.015, 0.5)
            put(f"ankle.{side}", 0.1 * s, 0.03, 0.085)
            put(f"toe.{side}", 0.105 * s, -0.12, 0.03)

    def bones(self):
        # (name, head, tail, parent, radius at head, radius at tail); parents first.
        j, k, w = self.joints, self.k, self.build
        bones = [
            ("hips", j["pelvis"], j["belly"], None, 0.15 * k, 0.13 * k),
            ("spine", j["belly"], j["chest"], "hips", 0.13 * k, 0.15 * k * w),
            ("chest", j["chest"], j["collar"], "spine", 0.15 * k * w, 0.13 * k * w),
            ("neck", j["neck"], j["skull"], "chest", 0.06 * k, 0.055 * k),
            ("head", j["skull"], j["crown"], "neck", 0.1 * k, 0.1 * k),
        ]
        for side, _ in SIDES:
            bones += [
                (f"shoulder.{side}", j[f"clavicle.{side}"], j[f"shoulder.{side}"], "chest", 0.07 * k * w, 0.06 * k * w),
                (f"upper_arm.{side}", j[f"shoulder.{side}"], j[f"elbow.{side}"], f"shoulder.{side}", 0.055 * k * w, 0.042 * k * w),
                (f"forearm.{side}", j[f"elbow.{side}"], j[f"wrist.{side}"], f"upper_arm.{side}", 0.042 * k * w, 0.031 * k * w),
                (f"hand.{side}", j[f"wrist.{side}"], j[f"knuckles.{side}"], f"forearm.{side}", 0.031 * k, 0.034 * k),
                (f"thigh.{side}", j[f"hip.{side}"], j[f"knee.{side}"], "hips", 0.085 * k * w, 0.055 * k),
                (f"shin.{side}", j[f"knee.{side}"], j[f"ankle.{side}"], f"thigh.{side}", 0.055 * k, 0.04 * k),
                (f"foot.{side}", j[f"ankle.{side}"], j[f"toe.{side}"], f"shin.{side}", 0.045 * k, 0.035 * k),
            ]
        return bones

    def skeleton(self):
        # The body the Skin modifier wraps, up to the neck (the head is its own mesh).
        j, k, w = self.joints, self.k, self.build
        nodes = [("pelvis", 0.15 * k), ("belly", 0.13 * k), ("chest", 0.155 * k * w), ("collar", 0.12 * k * w),
                 ("neck", 0.06 * k), ("skull", 0.055 * k)]
        edges = [("pelvis", "belly"), ("belly", "chest"), ("chest", "collar"), ("collar", "neck"), ("neck", "skull")]
        for side, _ in SIDES:
            nodes += [(f"shoulder.{side}", 0.062 * k * w), (f"elbow.{side}", 0.04 * k * w), (f"wrist.{side}", 0.03 * k),
                      (f"knuckles.{side}", 0.036 * k), (f"hip.{side}", 0.088 * k * w), (f"knee.{side}", 0.054 * k),
                      (f"ankle.{side}", 0.04 * k), (f"toe.{side}", 0.036 * k)]
            edges += [("collar", f"shoulder.{side}"), (f"shoulder.{side}", f"elbow.{side}"), (f"elbow.{side}", f"wrist.{side}"),
                      (f"wrist.{side}", f"knuckles.{side}"), ("pelvis", f"hip.{side}"), (f"hip.{side}", f"knee.{side}"),
                      (f"knee.{side}", f"ankle.{side}"), (f"ankle.{side}", f"toe.{side}")]
        names = [n for n, _ in nodes]
        return [(j[n], r) for n, r in nodes], [(names.index(a), names.index(b)) for a, b in edges]


# Fabrics, for the outfit material's "fabric" attribute.
SKIN, CLOTH, LEATHER, SATIN = 0.0, 1.0, 2.0, 3.0


def outfit_material():
    # One material for skin and clothes, told apart by the per-vertex
    # "fabric" attribute: skin scatters light below its pores, cloth has a
    # weave and creases, leather a grain, satin a glossy sheen.
    shader = Shader("Outfit")
    color = shader.node("ShaderNodeAttribute", attribute_name="outfit").outputs["Color"]
    fabric = shader.attribute("fabric")
    coords = shader.coords("Object")

    def band(low, high):
        return shader.math('MULTIPLY', shader.math('GREATER_THAN', fabric, low), shader.math('LESS_THAN', fabric, high))

    skin, cloth, leather, satin = band(-1, 0.5), band(0.5, 1.5), band(1.5, 2.5), band(2.5, 9)
    pores = shader.noise(coords, 2500.0, detail=3.0).outputs["Fac"]
    blotch = shader.noise(coords, 30.0, detail=3.0).outputs["Fac"]
    across = shader.math('SINE', shader.math('MULTIPLY', shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs[0], 2500.0))
    down = shader.math('SINE', shader.math('MULTIPLY', shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs[2], 2500.0))
    weave = shader.math('MULTIPLY', across, down)
    creases = shader.noise(shader.coords("Object", (6.0, 6.0, 2.0)), 8.0, detail=4.0, distortion=1.5).outputs["Fac"]
    grain = shader.voronoi(coords, 900.0, 'DISTANCE_TO_EDGE').outputs["Distance"]
    height = shader.math('ADD', shader.math('MULTIPLY', skin, shader.math('MULTIPLY', pores, 0.3)),
                         shader.math('MULTIPLY', cloth, shader.math('ADD', shader.math('MULTIPLY', weave, 0.15), shader.math('MULTIPLY', creases, 1.2))))
    height = shader.math('ADD', height, shader.math('MULTIPLY', leather, shader.math('ADD', grain, shader.math('MULTIPLY', creases, 0.8))))
    height = shader.math('ADD', height, shader.math('MULTIPLY', satin, shader.math('MULTIPLY', creases, 1.0)))
    color = shader.mix(shader.math('MULTIPLY', skin, 0.25), color, shader.mix(blotch, color, (0.75, 0.4, 0.35), 'MULTIPLY'))
    color = shader.mix(shader.math('MULTIPLY', cloth, 0.3), color, shader.mix(1.0, color, shader.ramp(creases, [(0.3, (0.75, 0.75, 0.75)), (0.7, (1.05, 1.05, 1.05))]), 'MULTIPLY'))
    roughness = shader.math('ADD', shader.math('ADD', shader.math('MULTIPLY', skin, 0.45), shader.math('MULTIPLY', cloth, 0.85)),
                            shader.math('ADD', shader.math('MULTIPLY', leather, 0.45), shader.math('MULTIPLY', satin, 0.22)))
    return shader.surface(color, roughness, shader.bump(height, 0.25, 0.003),
                          Subsurface_Weight=shader.math('MULTIPLY', skin, 0.3), Subsurface_Radius=(0.9, 0.35, 0.2),
                          Subsurface_Scale=0.02, Sheen_Weight=shader.math('ADD', shader.math('MULTIPLY', cloth, 0.15), shader.math('MULTIPLY', satin, 0.5)),
                          Anisotropic=shader.math('MULTIPLY', satin, 0.6))


def dress(body, main_bone, outfit):
    # outfit(position, normal, bone) -> (colour, fabric) for each vertex.
    colors, fabrics = [], []
    for vertex, bone in zip(body.data.vertices, main_bone):
        color, fabric = outfit(vertex.co, vertex.normal, bone)
        colors += [*color, 1.0]
        fabrics.append(fabric)
    body.data.color_attributes.new(name="outfit", type='FLOAT_COLOR', domain='POINT').data.foreach_set("color", colors)
    body.data.attributes.new(name="fabric", type='FLOAT', domain='POINT').data.foreach_set("value", fabrics)
    body.data.materials.append(outfit_material())


def skin_material(tone):
    # Skin for the head: freckled, blushed, scattering below the surface.
    shader = Shader("Face")
    coords = shader.coords("Object")
    pores = shader.noise(coords, 3000.0, detail=3.0).outputs["Fac"]
    blotch = shader.noise(coords, 25.0, detail=3.0).outputs["Fac"]
    color = shader.mix(blotch, tone, tuple(c * f for c, f in zip(tone, (1.05, 0.8, 0.78))))
    return shader.surface(color, 0.45, shader.bump(pores, 0.25, 0.0005), Subsurface_Weight=0.3,
                          Subsurface_Radius=(0.9, 0.35, 0.2), Subsurface_Scale=0.02)


def hair_material(color):
    # Strands combed back over the scalp.
    shader = Shader("Hair")
    strands = shader.noise(shader.coords("Object", (600.0, 60.0, 600.0)), 1.0, detail=4.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(strands, [(0.3, (0.6, 0.6, 0.6)), (0.7, (1.3, 1.3, 1.3))]), 'MULTIPLY')
    return shader.surface(color, 0.5, shader.bump(strands, 0.5, 0.001), Anisotropic=0.5, Specular_IOR_Level=0.3)


def add_head(rig, anatomy, tone, hair, hair_style="short", beard=None):
    # Skull, jaw, nose, ears, eyes, brows, lips and hair, all moving with the head.
    k = anatomy.k
    j = anatomy.joints
    centre = j["skull"] + Vector((0, -0.01, 0.075)) * k
    face = skin_material(tone)
    parts = [
        add_sphere("Skull", centre, 0.1 * k, face, scale=(0.88, 1.0, 1.1)),
        add_sphere("Jaw", centre + Vector((0, -0.035, -0.06)) * k, 0.07 * k, face, scale=(1.0, 1.05, 0.85)),
        add_sphere("Chin", centre + Vector((0, -0.085, -0.085)) * k, 0.025 * k, face),
        add_tube("Nose", [centre + Vector((0, -0.088, 0.01)) * k, centre + Vector((0, -0.112, -0.03)) * k],
                 [0.012 * k, 0.016 * k], face, sides=10),
    ]
    lips = Shader("Lips").surface(tuple(c * f for c, f in zip(tone, (0.85, 0.55, 0.55))), 0.3, Subsurface_Weight=0.3)
    parts.append(add_sphere("Lips", centre + Vector((0, -0.088, -0.065)) * k, 0.012 * k, lips, scale=(2.0, 0.6, 0.55)))
    brow = Shader("Brows").surface(tuple(0.6 * c for c in hair), 0.7)
    eye = eye_material((0.08, 0.12, 0.18))
    white = Shader("EyeWhite").surface((0.8, 0.78, 0.75), 0.1, Coat_Weight=1.0)
    for side, s in SIDES:
        socket = centre + Vector((0.034 * s, -0.082, 0.012)) * k
        parts.append(add_sphere(f"EyeWhite.{side}", socket, 0.0125 * k, white))
        parts.append(add_sphere(f"Iris.{side}", socket + Vector((0, -0.007, 0)) * k, 0.0068 * k, eye))
        parts.append(add_sphere(f"Brow.{side}", socket + Vector((0.004 * s, 0.002, 0.02)) * k, 0.016 * k, brow, scale=(1.3, 0.35, 0.3)))
        parts.append(add_sphere(f"Ear.{side}", centre + Vector((0.088 * s, 0.0, 0.0)) * k, 0.028 * k, face, scale=(0.35, 0.7, 1.0)))
    hair_coat = hair_material(hair)
    if hair_style == "short":
        parts.append(add_sphere("Hair", centre + Vector((0, 0.008, 0.012)) * k, 0.104 * k, hair_coat, scale=(0.9, 1.02, 1.08)))
    elif hair_style in ("topknot", "bun"):
        parts.append(add_sphere("Hair", centre + Vector((0, 0.01, 0.015)) * k, 0.103 * k, hair_coat, scale=(0.9, 1.02, 1.07)))
        if hair_style == "topknot":
            parts.append(add_sphere("Topknot", centre + Vector((0, 0.05, 0.11)) * k, 0.03 * k, hair_coat, scale=(0.8, 1.4, 0.8)))
        else:
            # A ballet bun, high at the back of the head.
            parts.append(add_sphere("Bun", centre + Vector((0, 0.09, 0.07)) * k, 0.038 * k, hair_coat, scale=(1.0, 0.85, 1.0)))
    elif hair_style == "shaved":
        parts.append(add_sphere("Hair", centre + Vector((0, 0.006, 0.01)) * k, 0.1015 * k, hair_coat, scale=(0.885, 1.005, 1.1)))
    if beard:
        parts.append(add_sphere("Beard", centre + Vector((0, -0.045, -0.075)) * k, 0.068 * k, hair_material(beard), scale=(1.0, 0.95, 0.75)))
    for part in parts:
        if part.name == "Hair":
            # A cap over the scalp: squash its lower half up inside the skull,
            # leaving the forehead and face bare but covering the back.
            r = part.data.vertices[0].co.length
            for vertex in part.data.vertices:
                floor = -0.7 * r if vertex.co.y > 0.2 * r else 0.25 * r if vertex.co.y < -0.6 * r else -0.2 * r
                vertex.co.z = max(vertex.co.z, floor)
        rigid(part, rig, "head")
    return parts


def build_person(name, anatomy, outfit):
    # The rigged, dressed body (without head). Returns the rig and the body.
    bones = anatomy.bones()
    rig = add_armature(f"{name}Rig", bones)
    body = skin_mesh(name, *anatomy.skeleton())
    main = bind(body, rig, [b for b in bones if b[0] != "head"])
    dress(body, main, outfit)
    return rig, body


def walk_pose(p):
    # A relaxed walk: legs swinging with the knee folding on the swing, arms
    # swinging against them, hips and shoulders counter-rotating.
    turns = {
        "hips": [("Z", 0.08 * math.sin(p)), ("Y", 0.03 * math.sin(p))],
        "spine": [("Z", -0.06 * math.sin(p))],
        "chest": [("Z", -0.06 * math.sin(p))],
        "neck": [("Z", 0.05 * math.sin(p))],
    }
    for side, s in SIDES:
        q = p + (0 if s > 0 else math.pi)
        turns[f"thigh.{side}"] = [("X", -0.42 * math.sin(q) - 0.05)]
        turns[f"shin.{side}"] = [("X", 0.1 + 0.75 * max(0.0, math.cos(q + 0.9)) ** 1.5)]
        turns[f"foot.{side}"] = [("X", -0.2 * math.sin(q + 0.4))]
        turns[f"upper_arm.{side}"] = [("X", 0.35 * math.sin(q)), ("Y", -s * 0.08)]
        turns[f"forearm.{side}"] = [("X", -0.25 - 0.15 * max(0.0, -math.sin(q)))]
    return turns, 0.022 * math.cos(2 * p)


def pose_at(keys, t):
    # keys: [(second, turns, offset, ease)], where ease shapes the move into
    # that key ("smooth", "snap" for a strike, "hold"). Returns the blended
    # pose as (pairs of turn lists with a factor), and the root offset.
    if t <= keys[0][0]:
        return keys[0][1], keys[0][1], 0.0, Vector(keys[0][2])
    for (t0, a, oa, _), (t1, b, ob, ease) in zip(keys, keys[1:]):
        if t <= t1:
            x = (t - t0) / (t1 - t0)
            if ease == "snap":
                x = 1 - (1 - x) ** 3
            elif ease == "windup":
                x = x * x * x
            else:
                x = smootherstep(x)
            return a, b, x, Vector(oa).lerp(Vector(ob), x)
    last = keys[-1]
    return last[1], last[1], 0.0, Vector(last[2])


def animate(rig, keys, walk_speed, walk_rate, camera_path, lens=40, fstop=2.8, idle=None, walk_seconds=None,
            spin=None, pivot=(0.0, 0.0)):
    # Walks forward (towards -Y) for walk_seconds (half the timeline unless
    # given; 0 for no walk), then stops and performs keys (timed from there),
    # blending in over half a second. idle(t) adds a little life (breathing,
    # bouncing) to the poses; spin(t) turns the whole body (radians) about
    # pivot, a spot on the floor in the body's own frame. camera_path(t,
    # position) gives the camera's location and the point it looks at,
    # around the person's position.
    scene = bpy.context.scene
    if walk_seconds is None:
        half = (scene.frame_start + scene.frame_end) // 2
    else:
        half = scene.frame_start + round(walk_seconds * FPS)
    mover = bpy.data.objects.new(name="Mover", object_data=None)
    bpy.context.collection.objects.link(mover)
    turner = bpy.data.objects.new(name="Pivot", object_data=None)
    bpy.context.collection.objects.link(turner)
    turner.parent = mover
    turner.location = (*pivot, 0.0)
    rig.parent = turner
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = lens
    camera_data.clip_start = 0.05
    camera_data.dof.use_dof = fstop > 0
    camera_data.dof.aperture_fstop = max(fstop, 0.1)
    camera = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera)
    focus = bpy.data.objects.new(name="Focus", object_data=None)
    bpy.context.collection.objects.link(focus)
    camera_data.dof.focus_object = focus
    track = camera.constraints.new(type='TRACK_TO')
    track.target = focus
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    scene.camera = camera
    rest = rest_frames(rig)
    distance, phase = 0.0, 0.0
    previous = scene.frame_start
    for frame in timeline_frames(step=1):
        dt = (frame - previous) / FPS
        previous = frame
        t = (frame - half) / FPS
        attack = smootherstep(t / 0.5) if half > scene.frame_start else 1.0
        distance += walk_speed * (1 - attack) * dt
        phase += 2 * math.pi * walk_rate * (1 - attack) * dt
        walk_turns, bob = walk_pose(phase)
        a, b, x, offset = pose_at(keys, max(t, 0.0))
        extra = idle(max(t, 0.0)) if idle else {}
        for bone in rig.pose.bones:
            bone_rest = rest[bone.name]
            striking = turn(bone_rest, a.get(bone.name, ())).slerp(turn(bone_rest, b.get(bone.name, ())), x)
            striking = turn(bone_rest, extra.get(bone.name, ())) @ striking
            bone.rotation_quaternion = turn(bone_rest, walk_turns.get(bone.name, ())).slerp(striking, attack)
            bone.keyframe_insert("rotation_quaternion", frame=frame)
        mover.location = (0, -distance, 0)
        mover.keyframe_insert("location", frame=frame)
        rig.location = Vector((-pivot[0], -pivot[1], 0)) + Vector((0, 0, bob)).lerp(offset, attack)
        rig.keyframe_insert("location", frame=frame)
        if spin:
            turner.rotation_euler = (0.0, 0.0, spin(max(t, 0.0)))
            turner.keyframe_insert("rotation_euler", frame=frame)
        eye, target = camera_path(t, Vector((0, -distance, 0)))
        camera.location = eye
        camera.keyframe_insert("location", frame=frame)
        focus.location = target
        focus.keyframe_insert("location", frame=frame)
    return distance


def metal_material(name, color, roughness=0.2, brushed=True):
    # Polished or brushed metal, with fine scratches.
    shader = Shader(name)
    scratches = shader.noise(shader.coords("Object", (1.0, 1.0, 300.0) if brushed else (1, 1, 1)), 400.0, detail=3.0).outputs["Fac"]
    rough = shader.math('ADD', roughness, shader.math('MULTIPLY', scratches, 0.15))
    return shader.surface(color, rough, shader.bump(scratches, 0.05, 0.0005), Metallic=1.0, Anisotropic=0.5 if brushed else 0.0)


def leather_material(name, color):
    shader = Shader(name)
    grain = shader.voronoi(shader.coords("Object"), 1200.0, 'DISTANCE_TO_EDGE').outputs["Distance"]
    wear = shader.noise(shader.coords("Object"), 30.0, detail=4.0).outputs["Fac"]
    color = shader.mix(wear, color, tuple(min(1.0, 1.6 * c) for c in color))
    return shader.surface(color, 0.5, shader.bump(grain, 0.3, 0.0005))


def floor_with(material, size=30):
    bpy.ops.mesh.primitive_plane_add(size=size)
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.data.materials.append(material)
    return floor
