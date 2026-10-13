import math

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


def set_world_color(color):
    background = bpy.context.scene.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (*color, 1.0)


def add_material(obj, name, color, roughness=0.5, transmission=0.0, ior=1.45):
    material = bpy.data.materials.new(name=name)
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["IOR"].default_value = ior
    obj.data.materials.append(material)
    return material


def add_point_light(location, energy):
    bpy.ops.object.light_add(type='POINT', location=location)
    light_object = bpy.context.active_object
    light_object.name = "Light"
    light_object.data.energy = energy
    return light_object


def add_orbit_camera(target, near, far, height):
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
    camera_data.dof.aperture_fstop = 2.8
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


def add_box(name, size, location, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation, scale=size)
    box = bpy.context.active_object
    box.name = name
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return box


def add_fluid_domain(size, location, cache_dir, resolution):
    domain = add_box("LiquidDomain", size, location)
    settings = domain.modifiers.new(name="Fluid", type='FLUID')
    settings.fluid_type = 'DOMAIN'
    domain_settings = settings.domain_settings
    domain_settings.domain_type = 'LIQUID'
    domain_settings.resolution_max = resolution
    domain_settings.use_mesh = True
    domain_settings.cache_type = 'ALL'
    domain_settings.cache_directory = cache_dir
    domain_settings.cache_frame_start = bpy.context.scene.frame_start
    domain_settings.cache_frame_end = bpy.context.scene.frame_end
    return domain


def add_liquid_inflow(radius, location, velocity):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location)
    inflow = bpy.context.active_object
    inflow.name = "LiquidInflow"
    inflow.hide_render = True
    settings = inflow.modifiers.new(name="Fluid", type='FLUID')
    settings.fluid_type = 'FLOW'
    flow_settings = settings.flow_settings
    flow_settings.flow_type = 'LIQUID'
    flow_settings.flow_behavior = 'INFLOW'
    flow_settings.use_initial_velocity = True
    flow_settings.velocity_coord = velocity
    return inflow


def add_collision(obj):
    settings = obj.modifiers.new(name="Fluid", type='FLUID')
    settings.fluid_type = 'EFFECTOR'
    settings.effector_settings.effector_type = 'COLLISION'


def bake_fluid(domain):
    with bpy.context.temp_override(object=domain, active_object=domain):
        bpy.ops.fluid.bake_all()


def basicliquid(cache_dir):
    clear_scene()
    set_timeline()
    set_world_color((0.4, 0.45, 0.5))

    domain = add_fluid_domain(size=(6, 4, 4), location=(0, 0, 2), cache_dir=cache_dir, resolution=64)
    add_material(domain, "Water", (0.6, 0.8, 1.0), roughness=0.05, transmission=1.0, ior=1.33)

    ramp = add_box("Ramp", size=(3, 2, 0.2), location=(-1.2, 0, 2), rotation=(0, math.radians(20), 0))
    add_material(ramp, "Ramp", (0.8, 0.25, 0.1), roughness=0.3)
    add_collision(ramp)

    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    add_material(bpy.context.active_object, "Floor", (0.3, 0.3, 0.32))

    add_liquid_inflow(radius=0.15, location=(-2.4, 0, 3.4), velocity=(1, 0, 0))

    focus = bpy.data.objects.new(name="Focus", object_data=None)
    bpy.context.collection.objects.link(focus)
    focus.location = (0, 0, 1)

    add_orbit_camera(focus, near=8, far=18, height=0.4)
    add_point_light(location=(0, 0, 8), energy=3000.0)

    bake_fluid(domain)
