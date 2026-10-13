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


def set_world_color(color):
    background = bpy.context.scene.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (*color, 1.0)


def add_material(obj, name, color, roughness=0.5):
    material = bpy.data.materials.new(name=name)
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    obj.data.materials.append(material)
    return material


def add_flickering_light(location, color, energy):
    # Volumes do not light the scene in EEVEE, so a light inside the
    # flames throws their glow onto the floor (but not onto the smoke).
    bpy.ops.object.light_add(type='POINT', location=location)
    light_object = bpy.context.active_object
    light_object.name = "FireLight"
    light_object.data.color = color
    light_object.data.volume_factor = 0.0
    light_object.data.driver_add("energy").driver.expression = (
        f"{energy} * (1 + 0.3 * sin(frame * 1.7) + 0.2 * sin(frame * 4.3))"
    )
    return light_object


def add_tracking_camera(target, location, lens):
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = lens
    camera_object = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera_object)
    camera_object.location = location
    track = camera_object.constraints.new(type='TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    bpy.context.scene.camera = camera_object
    return camera_object


def add_box(name, size, location):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, scale=size)
    box = bpy.context.active_object
    box.name = name
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return box


def add_fire_material(domain):
    # Dark smoke, with emission only where the simulation reports flame,
    # coloured from deep red at the edges to yellow-hot at the core.
    material = bpy.data.materials.new(name="Fire")
    tree = material.node_tree
    nodes, links = tree.nodes, tree.links
    nodes.remove(nodes["Principled BSDF"])

    volume = nodes.new(type="ShaderNodeVolumePrincipled")
    volume.inputs["Color"].default_value = (0.05, 0.05, 0.05, 1.0)
    volume.inputs["Density"].default_value = 2.0

    flame = nodes.new(type="ShaderNodeAttribute")
    flame.attribute_name = "flame"
    ramp = nodes.new(type="ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    elements[0].color = (0.0, 0.0, 0.0, 1.0)
    elements[1].color = (1.0, 0.7, 0.25, 1.0)
    for position, color in ((0.2, (0.6, 0.04, 0.0)), (0.45, (1.0, 0.2, 0.02)), (0.7, (1.0, 0.45, 0.08))):
        elements.new(position).color = (*color, 1.0)
    links.new(flame.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], volume.inputs["Emission Color"])

    strength = nodes.new(type="ShaderNodeMath")
    strength.operation = 'MULTIPLY'
    strength.inputs[1].default_value = 5.0
    links.new(flame.outputs["Fac"], strength.inputs[0])
    links.new(strength.outputs["Value"], volume.inputs["Emission Strength"])

    links.new(volume.outputs["Volume"], nodes["Material Output"].inputs["Volume"])
    domain.data.materials.append(material)
    return material


def add_fire_domain(size, location, cache_dir, resolution):
    domain = add_box("FireDomain", size, location)
    settings = domain.modifiers.new(name="Fluid", type='FLUID')
    settings.fluid_type = 'DOMAIN'
    domain_settings = settings.domain_settings
    domain_settings.domain_type = 'GAS'
    domain_settings.resolution_max = resolution
    domain_settings.use_noise = True
    domain_settings.noise_scale = 2
    domain_settings.vorticity = 0.3
    domain_settings.flame_vorticity = 1.0
    domain_settings.burning_rate = 0.4
    domain_settings.flame_smoke = 0.3
    domain_settings.use_dissolve_smoke = True
    domain_settings.dissolve_speed = 30
    domain_settings.cache_type = 'ALL'
    domain_settings.cache_directory = cache_dir
    domain_settings.cache_frame_start = bpy.context.scene.frame_start
    domain_settings.cache_frame_end = bpy.context.scene.frame_end
    add_fire_material(domain)
    return domain


def add_fire_flow(obj):
    # Emit fuel from the whole volume of the object so the flames start out
    # in its shape.
    obj.hide_render = True
    settings = obj.modifiers.new(name="Fluid", type='FLUID')
    settings.fluid_type = 'FLOW'
    flow_settings = settings.flow_settings
    flow_settings.flow_type = 'BOTH'
    flow_settings.flow_behavior = 'INFLOW'
    flow_settings.flow_source = 'MESH'
    flow_settings.volume_density = 1.0
    flow_settings.surface_distance = 0.1
    flow_settings.fuel_amount = 1.5
    flow_settings.subframes = 2


def bake_fluid(domain):
    with bpy.context.temp_override(object=domain, active_object=domain):
        bpy.ops.fluid.bake_all()


def basicfire(cache_dir):
    clear_scene()
    set_timeline()
    set_world_color((0.01, 0.01, 0.012))
    scene = bpy.context.scene
    scene.eevee.volumetric_tile_size = '4'
    scene.eevee.volumetric_samples = 128
    # AgX bleaches bright flames towards white; Standard keeps them orange.
    scene.view_settings.view_transform = 'Standard'

    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    add_material(bpy.context.active_object, "Floor", (0.1, 0.1, 0.1), roughness=0.4)

    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1.05))
    cube = bpy.context.active_object
    cube.name = "Cube"
    add_fire_flow(cube)
    domain = add_fire_domain(size=(5, 5, 9), location=(0, 0, 4.5), cache_dir=cache_dir, resolution=96)

    focus = bpy.data.objects.new(name="Focus", object_data=None)
    bpy.context.collection.objects.link(focus)
    focus.location = (0, 0, 3.2)

    add_tracking_camera(focus, location=(8.5, -8.5, 3.5), lens=35)
    add_flickering_light(location=(0, 0, 1.5), color=(1.0, 0.45, 0.1), energy=1500.0)
    add_glare(strength=0.8)

    bake_fluid(domain)
