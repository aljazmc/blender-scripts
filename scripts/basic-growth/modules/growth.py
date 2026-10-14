import math
import random

import bpy

from modules.nature import (FPS, Shader, MeshBuilder, Nodes, modifier_inputs, setup_stage, add_blade, add_leaf,
                            add_mover, add_wind, add_camera, keyframes, blade_material)

HEIGHT = 0.075  # full stem length, from the seed below ground
DEPTH = 0.015  # how deep the seed lies
HOOK = 0.012  # length of the hooked tip that pulls the seed leaves out

# The time-lapse, as {second: value} for each input of the plant's node group:
# the hooked shoot pushes up, straightens, opens its seed leaves and grows
# its first true leaves.
SCHEDULE = {
    "Growth": {0.0: 0.0, 1.0: 0.12, 4.0: 0.55, 5.5: 0.72, 10.0: 1.0},
    "Hook": {0.0: 1.0, 4.0: 1.0, 5.5: 0.0},
    "Open": {0.0: 0.0, 5.0: 0.0, 7.2: 1.0},
    "Leaves": {0.0: 0.0, 6.5: 0.0, 10.0: 1.0},
}


def stem_material():
    # Pale green, flushed red-purple towards the base, with a waxy sheen.
    shader = Shader("Stem")
    height = shader.node("ShaderNodeSeparateXYZ", {0: shader.node("ShaderNodeTexCoord").outputs["Object"]}).outputs[2]
    color = shader.ramp(height, [(0.0, (0.25, 0.06, 0.08)), (0.02, (0.35, 0.45, 0.12)), (0.06, (0.4, 0.6, 0.15))])
    streaks = shader.noise(shader.coords("Object", (400.0, 400.0, 20.0)), 1.0, detail=3.0).outputs["Fac"]
    color = shader.mix(1.0, color, shader.ramp(streaks, [(0.3, (0.85, 0.85, 0.85)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    return shader.surface(color, 0.35, shader.bump(streaks, 0.1, 0.0002), translucency=0.3, Sheen_Weight=0.3)


def leaf_material(name, light, dark, veins):
    # Translucent leaf with a pale midrib and side veins.
    shader = Shader(name)
    u, v = shader.uv()
    across = shader.math('ABSOLUTE', shader.math('SUBTRACT', u, 0.5))
    midrib = shader.math('LESS_THAN', across, 0.03)
    side = shader.math('GREATER_THAN', shader.math('SINE', shader.math('MULTIPLY', shader.math('SUBTRACT', v, across), 40.0)), 0.9)
    vein = shader.math('MULTIPLY', shader.math('MAXIMUM', midrib, shader.math('MULTIPLY', side, 0.6)), veins)
    mottle = shader.noise(shader.coords("Object"), 900.0, detail=4.0).outputs["Fac"]
    color = shader.mix(shader.math('MULTIPLY', v, 0.7), dark, light)
    color = shader.mix(vein, color, tuple(min(1.0, 1.4 * c) for c in light))
    color = shader.mix(1.0, color, shader.ramp(mottle, [(0.3, (0.85, 0.85, 0.85)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    return shader.surface(color, 0.4, shader.bump(shader.math('ADD', vein, shader.math('MULTIPLY', mottle, 0.3)), -0.2, 0.0003),
                          translucency=0.35, Specular_IOR_Level=0.5)


def coat_material():
    shader = Shader("SeedCoat")
    speckle = shader.noise(shader.coords("Object"), 2000.0, detail=4.0).outputs["Fac"]
    color = shader.ramp(speckle, [(0.35, (0.18, 0.1, 0.05)), (0.65, (0.35, 0.22, 0.12))])
    return shader.surface(color, 0.3, shader.bump(speckle, 0.2, 0.0002), Coat_Weight=0.5)


def hidden(obj):
    obj.hide_render = obj.hide_viewport = True
    return obj


def leaf_mesh(name, length, width, material, thickness=0.0):
    builder = MeshBuilder()
    add_leaf(builder, (0, 0, 0), (0, 1, 0), (0, 0, 1), length, width, rows=8)
    obj = builder.build(name, [material])
    if thickness:
        solid = obj.modifiers.new(name="Thickness", type='SOLIDIFY')
        solid.thickness = thickness
    return hidden(obj)


def coat_mesh(material):
    # Half a seed coat: a cupped shell around the closed seed leaves.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1)
    coat = bpy.context.active_object
    coat.name = "SeedCoatHalf"
    mesh = coat.data
    for vertex in mesh.vertices:
        x, y, z = vertex.co
        vertex.co = (0.0045 * x, 0.0075 * (y + 1) - 0.001, 0.0035 * max(z, 0.0))
    coat.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return hidden(coat)


def plant_nodes(stem, cotyledon, leaf, coat):
    # The seedling in geometry nodes, driven by Growth, Hook, Open and Leaves
    # (all 0..1) and swaying in a breeze that gusts over time.
    tree = Nodes("Seedling")
    for name in SCHEDULE:
        tree.socket(name, 'NodeSocketFloat', default=0.0)
    tree.socket("Geometry", 'NodeSocketGeometry', in_out='OUTPUT')
    node, math_node, vector = tree.node, tree.math, tree.vector
    source = node("NodeGroupInput").outputs
    out = node("NodeGroupOutput")

    line = node("GeometryNodeCurvePrimitiveLine", {"Start": (0.0, 0.0, -DEPTH), "End": (0.0, 0.0, HEIGHT - DEPTH)})
    line = node("GeometryNodeResampleCurve", {"Curve": line.outputs[0], "Count": 48})
    trimmed = node("GeometryNodeTrimCurve", {0: line.outputs[0], 3: math_node('MAXIMUM', source["Growth"], 0.002)}, mode='FACTOR')
    # Bend the top HOOK metres over into a half circle, as much as Hook says.
    along = node("GeometryNodeSplineParameter").outputs["Factor"]
    grown = math_node('MULTIPLY', math_node('MAXIMUM', source["Growth"], 0.002), HEIGHT)
    reached = math_node('MULTIPLY', along, grown)
    bend = math_node('MAXIMUM', math_node('SUBTRACT', HOOK, math_node('SUBTRACT', grown, reached)), 0.0)
    radius = HOOK / math.pi
    angle = math_node('DIVIDE', bend, radius)
    hooked = node("ShaderNodeCombineXYZ", {
        0: math_node('MULTIPLY', math_node('SUBTRACT', 1.0, math_node('COSINE', angle)), radius),
        2: math_node('ADD', math_node('ADD', -DEPTH, math_node('MINIMUM', reached, math_node('MAXIMUM', math_node('SUBTRACT', grown, HOOK), 0.0))),
                     math_node('MULTIPLY', math_node('SINE', angle), radius))}).outputs[0]
    position = node("GeometryNodeInputPosition").outputs[0]
    shaped = node("ShaderNodeMix", {0: source["Hook"], 4: position, 5: hooked}, data_type='VECTOR').outputs[1]
    # The breeze: a steady lean that gusts, plus a quick tremble, growing with height.
    seconds = node("GeometryNodeInputSceneTime").outputs["Seconds"]
    gust = node("ShaderNodeTexNoise", {"W": math_node('MULTIPLY', seconds, 0.6), "Scale": 1.0, "Detail": 2.0}, noise_dimensions='1D').outputs["Factor"]
    tremble = node("ShaderNodeTexNoise", {"W": math_node('MULTIPLY', seconds, 3.0), "Scale": 1.0, "Detail": 1.0}, noise_dimensions='1D').outputs["Color"]
    up = math_node('DIVIDE', math_node('MAXIMUM', node("ShaderNodeSeparateXYZ", {0: shaped}).outputs[2], 0.0), HEIGHT - DEPTH)
    sway = vector('ADD', vector('SCALE', (1.0, 0.25, 0.0), scale=math_node('MULTIPLY', math_node('SUBTRACT', gust, 0.3), 0.025)),
                  vector('SCALE', vector('SUBTRACT', tremble, (0.5, 0.5, 0.5)), scale=0.006))
    swayed = vector('ADD', shaped, vector('SCALE', sway, scale=math_node('MULTIPLY', up, up)))
    shoot = node("GeometryNodeSetPosition", {"Geometry": trimmed.outputs[0], "Position": swayed})
    thickness = math_node('MULTIPLY', 0.0011, math_node('SUBTRACT', 1.0, math_node('MULTIPLY', along, 0.35)))
    profile = node("GeometryNodeCurvePrimitiveCircle", {"Resolution": 10, "Radius": 1.0})
    body = node("GeometryNodeCurveToMesh", {"Curve": shoot.outputs[0], "Profile Curve": profile.outputs[0], "Scale": thickness, "Fill Caps": True})
    body = node("GeometryNodeSetMaterial", {"Geometry": body.outputs[0], "Material": stem})
    # Everything else hangs off the tip.
    tip = node("GeometryNodeSampleCurve", {"Curves": shoot.outputs[0], "Factor": 1.0}, mode='FACTOR', use_all_curves=True)
    index = node("GeometryNodeInputIndex").outputs[0]
    facing = node("FunctionNodeAlignRotationToVector", {"Vector": tip.outputs["Tangent"]}, axis='Y').outputs[0]
    flutter = math_node('MULTIPLY', math_node('SUBTRACT', node("ShaderNodeSeparateXYZ", {0: tremble}).outputs[1], 0.5), 0.3)

    def pair(instance, spin, tilt, scale, lift=0.0, selection=None):
        # Two of instance at the tip, half a turn apart about the stem,
        # tilted out by tilt (radians).
        at = vector('ADD', tip.outputs["Position"], vector('SCALE', tip.outputs["Tangent"], scale=lift))
        points = node("GeometryNodePoints", {"Count": 2, "Position": at})
        # Turned a little off square to the camera, so both pairs show.
        around = node("FunctionNodeEulerToRotation", {"Euler": node("ShaderNodeCombineXYZ", {
            1: math_node('ADD', spin + 0.6, math_node('MULTIPLY', index, math.pi))}).outputs[0]}).outputs[0]
        out_by = node("FunctionNodeEulerToRotation", {"Euler": node("ShaderNodeCombineXYZ", {0: math_node('MULTIPLY', tilt, -1.0)}).outputs[0]}).outputs[0]
        rotation = node("FunctionNodeRotateRotation", {"Rotation": facing, "Rotate By": around}, rotation_space='LOCAL').outputs[0]
        rotation = node("FunctionNodeRotateRotation", {"Rotation": rotation, "Rotate By": out_by}, rotation_space='LOCAL').outputs[0]
        inputs = {"Points": points.outputs[0], "Instance": node("GeometryNodeObjectInfo", {"Object": instance}).outputs["Geometry"],
                  "Rotation": rotation, "Scale": scale}
        if selection is not None:
            inputs["Selection"] = selection
        return node("GeometryNodeInstanceOnPoints", inputs).outputs[0]

    opening = source["Open"]
    seed_leaves = pair(cotyledon, 0.0, math_node('ADD', math_node('MULTIPLY', opening, 1.45), math_node('MULTIPLY', flutter, opening)),
                       math_node('ADD', 0.45, math_node('MULTIPLY', opening, 0.55)))
    true_leaves = pair(leaf, math.pi / 2, math_node('ADD', math_node('ADD', 0.15, math_node('MULTIPLY', source["Leaves"], 0.7)), flutter),
                       math_node('MAXIMUM', source["Leaves"], 0.001), lift=math_node('MULTIPLY', source["Leaves"], 0.004))
    shed = math_node('LESS_THAN', opening, 0.08)
    seed_coat = pair(coat, 0.0, math_node('MULTIPLY', opening, 3.0), 1.0, selection=shed)
    joined = node("GeometryNodeJoinGeometry")
    for part in (body.outputs[0], seed_leaves, true_leaves, seed_coat):
        tree.set(joined.inputs[0], part)
    tree.set(out.inputs[0], joined.outputs[0])
    return tree.group


def soil_material():
    # Moist, crumbly potting soil with bits of bark and grit.
    shader = Shader("Soil")
    coords = shader.coords("Object")
    crumbs = shader.voronoi(coords, 300.0)
    tone = shader.node("ShaderNodeSeparateColor", {0: crumbs.outputs["Color"]}).outputs[0]
    color = shader.ramp(tone, [(0.0, (0.012, 0.007, 0.004)), (0.7, (0.03, 0.017, 0.009)), (0.97, (0.07, 0.045, 0.025)), (1.0, (0.15, 0.13, 0.11))])
    clumps = shader.noise(coords, 40.0, detail=8.0, roughness=0.7).outputs["Fac"]
    height = shader.math('ADD', shader.math('MULTIPLY', crumbs.outputs["Distance"], -0.5), clumps)
    return shader.surface(color, 0.75, shader.bump(height, 0.8, 0.002))


def add_soil(rng):
    # Soil with real lumps, a few pebbles and a crack where the shoot comes up.
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=200, y_subdivisions=200, size=0.6)
    soil = bpy.context.active_object
    soil.name = "Soil"
    texture = bpy.data.textures.new(name="Clods", type='CLOUDS')
    texture.noise_scale = 0.012
    texture.noise_depth = 3
    lumps = soil.modifiers.new(name="Clods", type='DISPLACE')
    lumps.texture = texture
    lumps.strength = 0.004
    lumps.mid_level = 0.5
    soil.data.materials.append(soil_material())
    bpy.ops.object.shade_smooth()
    pebble = Shader("Pebble")
    grain = pebble.noise(pebble.coords("Object"), 800.0, detail=5.0).outputs["Fac"]
    pebble = pebble.surface(pebble.ramp(grain, [(0.3, (0.08, 0.07, 0.06)), (0.7, (0.2, 0.18, 0.15))]), 0.6, pebble.bump(grain, 0.3, 0.0003))
    for k in range(30):
        r = rng.uniform(0.012, 0.15)
        a = rng.uniform(0, 2 * math.pi)
        size = rng.uniform(0.001, 0.004)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=size, location=(r * math.cos(a), r * math.sin(a), 0.0))
        stone = bpy.context.active_object
        stone.scale = (rng.uniform(0.7, 1.3), rng.uniform(0.7, 1.3), rng.uniform(0.4, 0.8))
        stone.rotation_euler = (rng.random(), rng.random(), rng.random())
        stone.data.materials.append(pebble)
        bpy.ops.object.shade_smooth()
    return soil


def add_shed_coat(material, frame):
    # The seed coat, dropped on the soil once the seed leaves shrug it off.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1, location=(0.006, -0.004, 0.0008),
                                         rotation=(0.3, 2.6, 0.7), scale=(0.0045, 0.0075, 0.002))
    coat = bpy.context.active_object
    coat.name = "ShedCoat"
    coat.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    for at, hide in ((1, True), (frame, False)):
        coat.hide_render = coat.hide_viewport = hide
        coat.keyframe_insert("hide_render", frame=at)
        coat.keyframe_insert("hide_viewport", frame=at)


def add_backdrop(rng):
    # Out-of-focus garden behind: weeds close by, swaying, and bigger leafy
    # shapes further back for the bokeh.
    builder = MeshBuilder(attributes=("height", "tint"), groups=("wind",))
    for _ in range(400):
        x, y = rng.uniform(-0.3, 0.3), rng.uniform(0.08, 0.3)
        height = rng.uniform(0.02, 0.07)
        add_blade(builder, rng, x, y, height, height * 0.08, segments=4, tint=rng.random(), reach=0.08)
    weeds = builder.build("Weeds", [blade_material()])
    add_wind(weeds, add_mover("Gusts", (0.02, 0.0, 0.0)), add_mover("Flutter", (0.01, 0.0, 0.01)), size=0.1, strength=0.012)
    foliage = leaf_material("Foliage", (0.25, 0.42, 0.08), (0.1, 0.22, 0.03), 0.0)
    for k in range(14):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=rng.uniform(0.1, 0.25),
                                              location=(rng.uniform(-1.0, 1.0), rng.uniform(0.8, 1.6), rng.uniform(-0.15, 0.1)))
        bpy.context.active_object.data.materials.append(foliage)


def basicgrowth():
    sun = setup_stage(sun_elevation=25, sun_rotation=160, sun_energy=3.0, sky_strength=0.15)
    scene = bpy.context.scene
    rng = random.Random(21)
    # The sun creeps across the sky, as in a time-lapse.
    keyframes(sun, "rotation_euler", {1: (math.radians(70), 0, math.radians(130)), scene.frame_end: (math.radians(60), 0, math.radians(200))})
    add_soil(rng)
    add_backdrop(rng)
    stem = stem_material()
    cotyledon = leaf_mesh("Cotyledon", 0.017, 0.012, leaf_material("SeedLeaf", (0.45, 0.55, 0.12), (0.3, 0.42, 0.08), 0.3),
                          thickness=0.0008)
    leaf = leaf_mesh("TrueLeaf", 0.024, 0.02, leaf_material("TrueLeaf", (0.2, 0.45, 0.06), (0.1, 0.28, 0.03), 1.0))
    coat = coat_material()
    seedling = bpy.data.objects.new(name="Seedling", object_data=bpy.data.meshes.new(name="Seedling"))
    bpy.context.collection.objects.link(seedling)
    modifier = seedling.modifiers.new(name="Seedling", type='NODES')
    modifier.node_group = plant_nodes(stem, cotyledon, leaf, coat_mesh(coat))
    inputs = modifier_inputs(modifier)
    for name, schedule in SCHEDULE.items():
        for second, value in schedule.items():
            inputs[name].value = value
            inputs[name].keyframe_insert("value", frame=1 + round(second * FPS))
    add_shed_coat(coat, round(5.4 * FPS))
    camera, focus = add_camera((0.02, -0.2, 0.05), (0.0, 0.0, 0.012), lens=60, fstop=5.6)
    keyframes(focus, "location", {1: (0.0, 0.0, 0.008), round(5 * FPS): (0.0, 0.0, 0.03), scene.frame_end: (0.0, 0.0, 0.05)})
    keyframes(camera, "location", {1: (0.02, -0.2, 0.05), scene.frame_end: (-0.03, -0.21, 0.08)})
