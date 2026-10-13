import bpy


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


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


def basiccube():
    clear_scene()
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    add_camera(location=(7.35, -6.92, 4.95), rotation=(1.11, 0.05, 0.81))
    add_point_light(location=(0, 0, 5), energy=1000.0)
