import bpy

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


def add_material(obj, name, color, roughness=0.5):
    material = bpy.data.materials.new(name=name)
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    obj.data.materials.append(material)
    return material


def add_checker_material(obj, name, color1, color2, scale):
    material = bpy.data.materials.new(name=name)
    nodes = material.node_tree.nodes
    checker = nodes.new(type="ShaderNodeTexChecker")
    checker.inputs["Color1"].default_value = (*color1, 1.0)
    checker.inputs["Color2"].default_value = (*color2, 1.0)
    checker.inputs["Scale"].default_value = scale
    material.node_tree.links.new(checker.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    obj.data.materials.append(material)
    return material


def add_point_light(location, energy):
    bpy.ops.object.light_add(type='POINT', location=location)
    light_object = bpy.context.active_object
    light_object.name = "Light"
    light_object.data.energy = energy
    return light_object


def add_orbit_camera(target, near, far, height, fstop=2.8):
    # The pivot turns once around the target over the timeline while the
    # camera moves out-in-out-in-out along it, aimed and focused on the target.
    frames = bpy.context.scene.frame_end
    mid = (far + near) / 2
    amp = (far - near) / 2
    distance = f"({mid} + {amp} * cos(frame / {frames} * 4 * pi))"

    pivot = bpy.data.objects.new(name="CameraPivot", object_data=None)
    bpy.context.collection.objects.link(pivot)
    pivot.location = target.location
    pivot.driver_add("rotation_euler", 2).driver.expression = f"frame / {frames} * 2 * pi"

    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.dof.use_dof = True
    camera_data.dof.focus_object = target
    camera_data.dof.aperture_fstop = fstop
    camera_object = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera_object)
    camera_object.parent = pivot
    camera_object.driver_add("location", 1).driver.expression = f"-{distance}"
    camera_object.driver_add("location", 2).driver.expression = f"{height} * {distance}"

    track = camera_object.constraints.new(type='TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    bpy.context.scene.camera = camera_object
    return camera_object


def add_glare(strength):
    tree = bpy.data.node_groups.new(name="Compositor", type="CompositorNodeTree")
    tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type="NodeSocketColor")
    layers = tree.nodes.new(type="CompositorNodeRLayers")
    glare = tree.nodes.new(type="CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Strength"].default_value = strength
    output = tree.nodes.new(type="NodeGroupOutput")
    tree.links.new(layers.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"], output.inputs["Image"])
    bpy.context.scene.compositing_node_group = tree


def add_math(tree, operation, *inputs):
    node = tree.nodes.new(type="ShaderNodeMath")
    node.operation = operation
    for socket, value in zip(node.inputs, inputs):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return node.outputs["Value"]


def add_falloff(tree, value, width):
    # 1 at value 0, fading to 0 at value width.
    falloff = tree.nodes.new(type="ShaderNodeMapRange")
    tree.links.new(value, falloff.inputs["Value"])
    falloff.inputs["From Max"].default_value = width
    falloff.inputs["To Min"].default_value = 1.0
    falloff.inputs["To Max"].default_value = 0.0
    return falloff.outputs["Result"]


def add_nanosuit_material(obj, skin_color, suit_color, glow_color):
    # A ragged front sweeps up the cube and back down over the timeline,
    # turning the plain skin into glowing armour plates and back.
    frames = bpy.context.scene.frame_end
    material = bpy.data.materials.new(name="Nanosuit")
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links

    skin = nodes["Principled BSDF"]
    skin.inputs["Base Color"].default_value = (*skin_color, 1.0)
    skin.inputs["Roughness"].default_value = 0.3

    coords = nodes.new(type="ShaderNodeTexCoord").outputs["Object"]
    xyz = nodes.new(type="ShaderNodeSeparateXYZ")
    links.new(coords, xyz.inputs["Vector"])
    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.5
    links.new(coords, noise.inputs["Vector"])
    height = add_math(tree, 'MULTIPLY_ADD', noise.outputs["Fac"], 0.6, xyz.outputs["Z"])

    progress = nodes.new(type="ShaderNodeValue")
    progress.label = "Progress"
    progress.outputs["Value"].driver_add("default_value").driver.expression = (
        f"0.5 - 0.5 * cos(frame / {frames} * 2 * pi)"
    )
    front = add_math(tree, 'MULTIPLY_ADD', progress.outputs["Value"], 2.9, -1.2)

    covered = add_math(tree, 'LESS_THAN', height, front)
    edge = add_falloff(tree, add_math(tree, 'ABSOLUTE', add_math(tree, 'SUBTRACT', height, front)), 0.12)

    plates = nodes.new(type="ShaderNodeTexVoronoi")
    plates.feature = 'DISTANCE_TO_EDGE'
    plates.inputs["Scale"].default_value = 6.0
    links.new(coords, plates.inputs["Vector"])
    seams = add_falloff(tree, plates.outputs["Distance"], 0.04)
    bump = nodes.new(type="ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    links.new(add_math(tree, 'SUBTRACT', 1.0, seams), bump.inputs["Height"])

    suit = nodes.new(type="ShaderNodeBsdfPrincipled")
    suit.inputs["Base Color"].default_value = (*suit_color, 1.0)
    suit.inputs["Metallic"].default_value = 1.0
    suit.inputs["Roughness"].default_value = 0.35
    suit.inputs["Emission Color"].default_value = (*glow_color, 1.0)
    links.new(add_math(tree, 'MULTIPLY', seams, 4.0), suit.inputs["Emission Strength"])
    links.new(bump.outputs["Normal"], suit.inputs["Normal"])

    mix = nodes.new(type="ShaderNodeMixShader")
    links.new(covered, mix.inputs["Fac"])
    links.new(skin.outputs["BSDF"], mix.inputs[1])
    links.new(suit.outputs["BSDF"], mix.inputs[2])

    glow = nodes.new(type="ShaderNodeEmission")
    glow.inputs["Color"].default_value = (*glow_color, 1.0)
    links.new(add_math(tree, 'MULTIPLY', edge, 30.0), glow.inputs["Strength"])

    surface = nodes.new(type="ShaderNodeAddShader")
    links.new(mix.outputs["Shader"], surface.inputs[0])
    links.new(glow.outputs["Emission"], surface.inputs[1])
    links.new(surface.outputs["Shader"], nodes["Material Output"].inputs["Surface"])

    obj.data.materials.append(material)
    return material


def basicnanosuit():
    clear_scene()
    set_timeline()
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -1))
    add_checker_material(bpy.context.active_object, "Floor", (0.35, 0.35, 0.38), (0.15, 0.15, 0.17), scale=20)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.name = "Cube"
    add_nanosuit_material(cube, skin_color=(0.8, 0.25, 0.1), suit_color=(0.04, 0.045, 0.05), glow_color=(0.1, 0.7, 1.0))
    add_orbit_camera(cube, near=6, far=16, height=0.4)
    add_point_light(location=(0, 0, 5), energy=1000.0)
    add_glare(strength=0.6)
