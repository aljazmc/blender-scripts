from mathutils import Vector

from modules.nature import Shader, setup_stage, add_meadow
from modules.body import SIDES, add_tube, rigid, lerp, smootherstep
from modules.quadruped import Anatomy, build_animal, add_face, add_hooves, ear_material, animate

ANATOMY = dict(
    length=0.8, height=1.0, width=0.09,
    chest=0.19, waist=0.15, hips=0.15,
    neck=(0.36, 45, 0.14, 0.075),
    head=(0.14, 0.075),
    snout=(0.15, 0.04, 0.04),
    legs=(0.06, 0.02, 0.022),
    tail=(0.14, 0.04, 25),
    front=(0.6, 0.3), hind=(0.64, 0.4),
)

BROWN = (0.3, 0.15, 0.06)
DARK = (0.14, 0.07, 0.03)
WHITE = (0.72, 0.68, 0.6)
GREY = (0.22, 0.17, 0.13)


def mix(a, b, factor):
    return tuple(lerp(x, y, factor) for x, y in zip(a, b))


def coat(position, normal, bone):
    # Short tawny coat, darker along the spine, with a white belly, throat
    # patch, muzzle band and the white underside of the tail.
    under = smootherstep((-normal.z - 0.2) / 0.5)
    top = smootherstep((normal.z - 0.3) / 0.5)
    if bone.startswith(("upper", "lower", "foot", "tail")):
        # Limbs and tail keep their own colours; no belly patch where they join.
        under = 0.0
    # Only the underside proper, not the folds where the legs meet the body.
    under *= smootherstep((0.68 * ANATOMY["height"] - position.z) / (0.08 * ANATOMY["height"]))
    color = mix(mix(BROWN, DARK, top), WHITE, under)
    length, tip = 0.018, 0.0
    if bone == "neck":
        throat = smootherstep((-normal.y - 0.3) / 0.4) * smootherstep((position.z - 1.15) / 0.05)
        color, length = mix(mix(BROWN, GREY, 0.4), WHITE, throat), 0.025
    elif bone == "head":
        color, length = mix(GREY, WHITE, smootherstep((-normal.z + 0.1) / 0.4)), 0.012
    elif bone == "snout":
        color, length = mix(DARK, WHITE, smootherstep((-normal.z + 0.3) / 0.4)), 0.006
    elif bone.startswith("tail"):
        color, length = (WHITE if normal.y > -0.2 and normal.z < 0.3 else DARK), 0.05
    elif bone.startswith(("lower", "foot")):
        color, length = mix(mix(BROWN, GREY, 0.3), WHITE, 0.6 * under), 0.008
    return color, length, tip


def antler_material():
    # Pale, polished tips over a ridged, darker beam.
    shader = Shader("Antler")
    ridges = shader.noise(shader.coords("Object", (60.0, 60.0, 8.0)), 10.0, detail=6.0).outputs["Fac"]
    height = shader.node("ShaderNodeSeparateXYZ", {0: shader.node("ShaderNodeTexCoord").outputs["Generated"]}).outputs[2]
    color = shader.ramp(height, [(0.2, (0.16, 0.11, 0.07)), (0.85, (0.55, 0.47, 0.36)), (1.0, (0.75, 0.7, 0.6))])
    color = shader.mix(1.0, color, shader.ramp(ridges, [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.1, 1.1, 1.1))]), 'MULTIPLY')
    return shader.surface(color, 0.55, shader.bump(ridges, 0.6, 0.002))


def add_antlers(rig, bvh, anatomy):
    # Two beams sweeping up, back and forward, each with tines rising off it.
    material = antler_material()
    skull = anatomy.joints["skull"]
    r = anatomy.head_radius
    for side, s in SIDES:
        base = bvh.find_nearest(skull + Vector((0.45 * r * s, 0.1 * r, 1.1 * r)))[0]
        beam = [base]
        heading = Vector((0.45 * s, 0.35, 1.0)).normalized()
        for k in range(8):
            heading = (heading + Vector((0.03 * s, -0.12, -0.02))).normalized()
            beam.append(beam[-1] + heading * 0.05)
        radii = [0.016 * (1 - 0.7 * k / 8) for k in range(9)]
        rigid(add_tube(f"Antler.{side}", beam, radii, material), rig, "head")
        for t, (lean, length) in enumerate(((0.1, 0.12), (0.0, 0.16), (-0.1, 0.11))):
            start = beam[2 + 2 * t]
            up = Vector((0.1 * s, lean, 1.0)).normalized()
            tine = [start + up * (length * k / 4) + Vector((0, -0.02 * (k / 4) ** 2, 0)) for k in range(5)]
            rigid(add_tube(f"Tine.{side}.{t}", tine, [0.009 * (1 - 0.75 * k / 4) for k in range(5)], material, sides=8), rig, "head")
    return [(skull + Vector((0, 0, r)), 0.25 * r)]


def basicdeer():
    setup_stage(sun_elevation=25, sun_rotation=-110, sun_energy=4.5, sky_strength=0.2)
    anatomy = Anatomy(**ANATOMY)
    rig, bvh, grow_fur = build_animal("Deer", anatomy, coat, tip_color=(0.05, 0.03, 0.02),
                                            density=140000.0, radius=0.0004)
    features = add_face(rig, bvh, anatomy, ear_material((0.2, 0.14, 0.09), (0.55, 0.45, 0.4)),
                        ear_size=(0.16, 0.1), ear_spread=0.9, ear_tilt=0.35, eye_size=0.016)
    features += add_hooves(rig, anatomy)
    features += add_antlers(rig, bvh, anatomy)
    fur = grow_fur(features)
    distance = animate(rig, fur, walk_speed=1.2, run_speed=9.0, walk_rate=0.9, run_rate=2.3,
                       camera_distance=4.4, camera_height=1.0)
    add_meadow(distance)
