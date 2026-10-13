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


def add_camera(location, rotation):
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_object = bpy.data.objects.new(name="Camera", object_data=camera_data)
    bpy.context.collection.objects.link(camera_object)
    camera_object.location = location
    camera_object.rotation_euler = rotation
    bpy.context.scene.camera = camera_object
    return camera_object


def add_point_light(location, energy):
    bpy.ops.object.light_add(type='POINT', location=location)
    light_object = bpy.context.active_object
    light_object.name = "Light"
    light_object.data.energy = energy
    return light_object


def add_floating_particles(instance, size, count):
    # All particles are born on the first frame and live past the last one;
    # without gravity they drift, wobble and spin in place.
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_cube_add(size=size, location=(0, 0, 0))
    emitter = bpy.context.active_object
    emitter.name = "Emitter"
    emitter.show_instancer_for_render = False
    emitter.show_instancer_for_viewport = False
    emitter.modifiers.new(name="Particles", type='PARTICLE_SYSTEM')

    settings = emitter.particle_systems[0].settings
    settings.count = count
    settings.frame_start = scene.frame_start
    settings.frame_end = scene.frame_start
    settings.lifetime = scene.frame_end + 1
    settings.emit_from = 'VOLUME'
    settings.distribution = 'RAND'
    settings.normal_factor = 0.0
    settings.factor_random = 0.3
    settings.brownian_factor = 0.2
    settings.effector_weights.gravity = 0.0
    settings.render_type = 'OBJECT'
    settings.instance_object = instance
    settings.particle_size = 0.1
    settings.size_random = 0.6
    settings.use_rotations = True
    settings.rotation_factor_random = 1.0
    settings.angular_velocity_mode = 'RAND'
    settings.angular_velocity_factor = 2.0
    return emitter


def make_particles_real(emitter, frame):
    # Particles are not exported by glTF, so turn them into real objects
    # at the given frame and drop the emitter and its instanced cube.
    scene = bpy.context.scene
    for f in range(scene.frame_start, frame + 1):
        scene.frame_set(f)
    instance = emitter.particle_systems[0].settings.instance_object
    bpy.ops.object.select_all(action='DESELECT')
    emitter.select_set(True)
    bpy.context.view_layer.objects.active = emitter
    bpy.ops.object.duplicates_make_real()
    bpy.data.objects.remove(emitter)
    bpy.data.objects.remove(instance)


def basicparticles():
    clear_scene()
    set_timeline()
    # The instanced cube sits far below the camera's view.
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, -100))
    cube = bpy.context.active_object
    cube.name = "Cube"
    add_material(cube, "Cube", (0.8, 0.25, 0.1), roughness=0.3)
    emitter = add_floating_particles(cube, size=6, count=300)
    add_camera(location=(7.35, -6.92, 4.95), rotation=(1.11, 0.05, 0.81))
    add_point_light(location=(0, 0, 5), energy=1000.0)
    return emitter
