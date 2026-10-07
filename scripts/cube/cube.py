import bpy

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

bpy.ops.wm.save_as_mainfile(filepath="/home/aljazmc/Projects/sh/blender-scripts/scripts/cube/cube.blend")

bpy.ops.export_scene.gltf(
    filepath="/home/aljazmc/Projects/sh/blender-scripts/scripts/cube/cube.gltf",
    export_format="GLTF_SEPARATE",
    use_active_collection =True
)

camera_data = bpy.data.cameras.new(name="Camera")
camera_object = bpy.data.objects.new(name="Camera", object_data=camera_data)

bpy.context.collection.objects.link(camera_object)

camera_object.location = (7.35, -6.92, 4.95)
camera_object.rotation_euler = (1.11, 0.05, 0.81)

bpy.context.scene.camera = camera_object

bpy.ops.object.light_add(type='POINT', location=(0, 0, 5))

light_object = bpy.context.active_object
light_object.name = "Light"
light_object.data.energy = 1000.0

bpy.ops.wm.save_as_mainfile(filepath="/home/aljazmc/Projects/sh/blender-scripts/scripts/cube/cube.blend")

bpy.context.scene.render.filepath = "/home/aljazmc/Projects/sh/blender-scripts/scripts/cube/cube.mp4"

bpy.context.scene.render.image_settings.media_type = 'VIDEO'
bpy.context.scene.render.ffmpeg.format = 'MPEG4'
bpy.context.scene.render.ffmpeg.codec = 'H264'

bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.fps = 24

bpy.ops.render.render(animation=True)

