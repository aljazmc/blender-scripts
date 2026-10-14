import math

import bpy
from mathutils import Vector

from modules.nature import Shader, MeshBuilder, clear_scene, set_timeline, overcast
from modules.body import SIDES, smootherstep, rigid, add_tube
from modules.humanoid import SKIN, CLOTH, SATIN, Anatomy, build_person, add_head, animate

TONE = (0.62, 0.42, 0.33)
BODICE = (0.7, 0.32, 0.38)
TIGHTS = (0.78, 0.55, 0.48)
SHOES = (0.8, 0.52, 0.48)
PIROUETTE = (4.25, 5.35)  # seconds when the double turn starts and ends


def outfit(position, normal, bone):
    # A satin bodice, pink tights and pointe shoes; bare arms and shoulders.
    z = position.z
    if bone.startswith("foot") or (bone.startswith("shin") and z < 0.1):
        return SHOES, SATIN
    if bone.startswith(("thigh", "shin")):
        return TIGHTS, CLOTH
    if bone in ("hips", "spine") or (bone == "chest" and z < 1.33):
        return BODICE, SATIN
    return TONE, SKIN


def turnout(turns, flat=True):
    # Legs rotated out from the hip, as ballet stands.
    for side, s in SIDES:
        turns.setdefault(f"thigh.{side}", []).insert(0, ("Z", s * 0.75))
        turns.setdefault(f"foot.{side}", []).append(("X", 0.15 if flat else 1.25))
    return turns


ARMS = {
    # Port de bras, as (upper arm, forearm) turns for the left arm; mirrored for the right.
    "low": ([("X", -0.15), ("Y", 0.12)], [("X", -0.45), ("Z", -0.5)]),
    "first": ([("X", -0.85), ("Y", 0.1)], [("X", -0.7), ("Z", -0.75)]),
    "second": ([("Y", -1.25), ("X", -0.25)], [("X", -0.3), ("Z", -0.3)]),
    "high": ([("Y", -0.4), ("X", -2.75)], [("X", -0.55), ("Z", -0.6)]),
    "forward": ([("X", -1.75), ("Y", -0.1)], [("X", -0.15)]),
}


def arms(turns, left, right=None):
    for side, s in SIDES:
        upper, fore = ARMS[left if s > 0 else (right or left)]
        turns[f"upper_arm.{side}"] = [(axis, angle * (s if axis in "YZ" else 1)) for axis, angle in upper]
        turns[f"forearm.{side}"] = [(axis, angle * (s if axis in "YZ" else 1)) for axis, angle in fore]
        turns[f"hand.{side}"] = [("X", -0.08), ("Z", -s * 0.15)]
    return turns


def fifth(arm="low"):
    # Standing tall, heels together, feet turned out.
    return arms(turnout({"neck": [("X", -0.05)], "head": [("Z", -0.15)]}), arm)


def plie(arm="second", depth=0.5):
    turns = arms(turnout({"spine": [("X", -0.03)]}), arm)
    for side, _ in SIDES:
        # Bend first, then turn out, so the knees open over the toes.
        turns[f"thigh.{side}"].insert(0, ("X", -depth))
        turns[f"shin.{side}"] = [("X", 2 * depth)]
        turns[f"foot.{side}"] = [("X", 0.15 - depth)]
    return turns


def releve(arm="high"):
    # Up on pointe.
    turns = arms(turnout({"neck": [("X", -0.12)]}, flat=False), arm)
    return turns


def passe():
    # Retire for the pirouette: the right foot drawn up to the left knee,
    # standing on pointe, arms rounded in front.
    turns = arms(turnout({"neck": [("Z", 0.0)]}, flat=False), "first")
    turns["thigh.R"] = [("Z", -0.8), ("Y", 0.75), ("X", -0.85)]
    turns["shin.R"] = [("X", 2.3)]
    turns["foot.R"] = [("X", 1.1)]
    turns["thigh.L"] = [("Z", 0.4)]
    return turns


def fourth():
    # Preparation and landing: plie in fourth, right foot behind.
    turns = plie("first", 0.35)
    turns["thigh.R"] = [("Z", -0.75), ("X", 0.25)]
    turns["shin.R"] = [("X", 0.6)]
    turns["thigh.L"] = [("Z", 0.75), ("X", -0.6)]
    return turns


def arabesque():
    # On the left leg, the right stretched long behind and up, the body
    # tipped forward, left arm reaching ahead and right arm to the side.
    turns = arms(turnout({"spine": [("X", 0.35)], "chest": [("X", 0.1)], "neck": [("X", -0.45)]}, flat=False), "forward", "second")
    turns["thigh.R"] = [("Z", -0.6), ("X", 1.35)]
    turns["shin.R"] = [("X", 0.0)]
    turns["foot.R"] = [("X", 1.2)]
    turns["thigh.L"] = [("Z", 0.6)]
    return turns


def reverence():
    # The closing bow: a soft plie, head and arms lowered.
    turns = plie("second", 0.3)
    turns["spine"] = [("X", 0.45)]
    turns["chest"] = [("X", 0.15)]
    turns["neck"] = [("X", 0.35)]
    for side, s in SIDES:
        turns[f"upper_arm.{side}"] = [("Y", -s * 0.7), ("X", 0.1)]
    return turns


KEYS = [
    (0.0, fifth("low"), (0, 0, 0.0), "smooth"),
    (0.6, fifth("low"), (0, 0, 0.0), "smooth"),
    (1.3, fifth("first"), (0, 0, 0.0), "smooth"),
    (2.0, plie("second", 0.55), (0, 0, -0.13), "smooth"),
    (2.8, releve("high"), (0, 0, 0.11), "smooth"),
    (3.4, releve("high"), (0, 0, 0.11), "smooth"),
    (4.0, fourth(), (0, 0.03, -0.08), "smooth"),
    (4.25, passe(), (0, 0, 0.11), "snap"),
    (5.35, passe(), (0, 0, 0.11), "smooth"),
    (5.65, fourth(), (0, 0.03, -0.08), "smooth"),
    (6.6, arabesque(), (0, 0.08, 0.11), "smooth"),
    (7.8, arabesque(), (0, 0.08, 0.11), "smooth"),
    (8.5, fifth("low"), (0, 0, 0.0), "smooth"),
    (9.3, reverence(), (0, 0, -0.06), "smooth"),
    (10.0, reverence(), (0, 0, -0.06), "smooth"),
]


def spin(t):
    # The double pirouette, two turns to the right; then a quarter turn into
    # profile for the arabesque, and back to face the audience for the bow.
    start, end = PIROUETTE
    turns = -4 * math.pi * smootherstep((t - start) / (end - start))
    profile = smootherstep((t - 5.7) / 0.8) - smootherstep((t - 7.9) / 0.6)
    return turns - 0.5 * math.pi * profile


def breathe(t):
    b = math.sin(2 * math.pi * 0.5 * t)
    return {"chest": [("X", -0.015 * b)], "neck": [("Z", 0.03 * math.sin(2 * math.pi * 0.2 * t))]}


def tulle_material():
    # Layers of stiff net: a fine mesh that light shines through.
    shader = Shader("Tulle")
    coords = shader.coords("Object")
    x, y, _ = shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs
    net = shader.math('MULTIPLY', shader.math('SINE', shader.math('MULTIPLY', x, 900.0)), shader.math('SINE', shader.math('MULTIPLY', y, 900.0)))
    holes = shader.math('GREATER_THAN', net, 0.55)
    return shader.surface((0.85, 0.68, 0.7), 0.6, Sheen_Weight=0.6,
                          Alpha=shader.math('SUBTRACT', 0.9, shader.math('MULTIPLY', holes, 0.6)))


def add_tutu(rig, anatomy):
    # A classical tutu: stacked, ruffled discs of net standing out from the hips.
    k = anatomy.k
    waist = anatomy.joints["pelvis"] + Vector((0, 0, 0.02)) * k
    builder = MeshBuilder()
    rings, sectors = 6, 64
    for layer in range(7):
        inner, outer = 0.135 * k, (0.36 - 0.012 * layer) * k
        z0 = waist.z - 0.012 * k * layer
        verts, faces = [], []
        for r in range(rings + 1):
            f = r / rings
            radius = inner + (outer - inner) * f
            for i in range(sectors):
                a = 2 * math.pi * i / sectors
                ruffle = 0.012 * k * f * math.sin(a * 11 + layer * 1.7)
                verts.append((radius * math.cos(a) * 1.05, radius * math.sin(a) * 0.95, z0 - 0.03 * k * f * f + ruffle))
        for r in range(rings):
            for i in range(sectors):
                j = (i + 1) % sectors
                faces.append([r * sectors + i, r * sectors + j, (r + 1) * sectors + j, (r + 1) * sectors + i])
        builder.add(verts, faces)
    tutu = builder.build("Tutu", [tulle_material()])
    rigid(tutu, rig, "hips")
    return tutu


def add_ribbons(rig, anatomy):
    # The pointe shoe ribbons, wrapped round each ankle.
    satin = Shader("Ribbon").surface(SHOES, 0.25, Sheen_Weight=0.5, Anisotropic=0.6)
    k = anatomy.k
    for side, s in SIDES:
        ankle = anatomy.joints[f"ankle.{side}"]
        for level, lift in enumerate((0.03, 0.06)):
            centre = ankle + Vector((0, 0, lift)) * k
            ring = [centre + Vector((0.044 * math.cos(a), 0.044 * math.sin(a), 0.012 * math.sin(a + level))) * k
                    for a in [i * 2 * math.pi / 16 for i in range(17)]]
            rigid(add_tube(f"Ribbon.{side}.{level}", ring, [0.004 * k] * 17, satin, sides=6), rig, f"shin.{side}")


def stage_material():
    # A black dance floor: matt vinyl with scuffs from rosin and shoes.
    shader = Shader("Marley")
    coords = shader.coords("Object")
    scuffs = shader.noise(coords, 6.0, detail=6.0, roughness=0.6).outputs["Fac"]
    fine = shader.noise(coords, 400.0, detail=3.0).outputs["Fac"]
    color = shader.ramp(scuffs, [(0.4, (0.015, 0.015, 0.016)), (0.7, (0.05, 0.05, 0.05))])
    roughness = shader.math('ADD', 0.25, shader.math('MULTIPLY', scuffs, 0.4))
    return shader.surface(color, roughness, shader.bump(fine, 0.05, 0.001))


def curtain_material():
    # Deep red velvet that glows at the edges of its folds.
    shader = Shader("Velvet")
    folds = shader.node("ShaderNodeTexWave", {"Vector": shader.coords("Object"), "Scale": 6.0, "Distortion": 2.0},
                        bands_direction='X').outputs["Fac"]
    color = shader.ramp(folds, [(0.0, (0.03, 0.002, 0.004)), (1.0, (0.18, 0.01, 0.02))])
    return shader.surface(color, 0.9, shader.bump(folds, 0.6, 0.05), Sheen_Weight=1.0, Sheen_Tint=(0.8, 0.3, 0.3))


def add_stage():
    bpy.ops.mesh.primitive_plane_add(size=20)
    bpy.context.active_object.name = "Stage"
    bpy.context.active_object.data.materials.append(stage_material())
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 5, 3), rotation=(math.pi / 2, 0, 0))
    curtain = bpy.context.active_object
    curtain.name = "Curtain"
    curtain.scale = (20, 6, 1)
    curtain.data.materials.append(curtain_material())
    # A warm spotlight from the front, a cool one from above and behind for the rim.
    for name, location, energy, color, size in (("Spot", (-2.5, -6.0, 6.0), 3000.0, (1.0, 0.9, 0.78), 0.3),
                                                ("Back", (1.5, 3.0, 5.5), 2000.0, (0.7, 0.8, 1.0), 0.3)):
        data = bpy.data.lights.new(name=name, type='SPOT')
        data.energy, data.color, data.shadow_soft_size = energy, color, size
        data.spot_size, data.spot_blend = math.radians(28), 0.4
        light = bpy.data.objects.new(name=name, object_data=data)
        bpy.context.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (Vector((0, 0, 1.0)) - light.location).to_track_quat('-Z', 'Y').to_euler()


def camera_path(t, position):
    # A slow arc round the front of the stage, closing in a little.
    a = math.radians(-25 + 30 * t / 10)
    distance = 4.6 - 0.8 * t / 10
    eye = position + Vector((distance * math.sin(a), -distance * math.cos(a), 1.25))
    return eye, position + Vector((0, 0, 1.0))


def basicdancer():
    clear_scene()
    set_timeline()
    overcast(color=(0.005, 0.005, 0.006), strength=1.0)
    bpy.context.scene.view_settings.look = 'AgX - Medium High Contrast'
    anatomy = Anatomy(height=1.66, build=0.85)
    rig, _ = build_person("Dancer", anatomy, outfit)
    add_head(rig, anatomy, TONE, hair=(0.05, 0.03, 0.015), hair_style="bun")
    add_tutu(rig, anatomy)
    add_ribbons(rig, anatomy)
    add_stage()
    animate(rig, KEYS, walk_speed=0.0, walk_rate=0.0, camera_path=camera_path, lens=45, fstop=2.8, idle=breathe,
            walk_seconds=0, spin=spin, pivot=(0.09 * anatomy.k, 0.0))
