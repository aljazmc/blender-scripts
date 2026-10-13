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


def basiccamera():
    clear_scene()
    set_timeline()
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -1))
    add_checker_material(bpy.context.active_object, "Floor", (0.35, 0.35, 0.38), (0.15, 0.15, 0.17), scale=20)
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.active_object
    cube.name = "Cube"
    add_material(cube, "Cube", (0.8, 0.25, 0.1), roughness=0.3)
    add_orbit_camera(cube, near=6, far=16, height=0.4)
    add_point_light(location=(0, 0, 5), energy=1000.0)
