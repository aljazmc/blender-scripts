import math
import random

import bpy
from mathutils import Vector

from modules.nature import Shader, MeshBuilder, setup_stage, add_leaf, add_mover, add_displace, add_camera, keyframes

PAGE_WIDTH = 0.15
PAGE_HEIGHT = 0.22
BOARD = 0.0035  # cover thickness; the pages rest on top of it
HINGE = BOARD + 0.0015  # where the pages are sewn into the spine
LEAF_GAP = 0.0003  # spacing between loose pages
STAGES = 24  # shape keys per page, from lying right (0) to lying left (1)

# Gusts lifting the loose pages, as {frame: flip}. Each page stays below the
# one above it: 0 lies on the right-hand stack, 1 on the left.
FLIPS = [
    {1: 0.0, 10: 0.0, 22: 0.08, 32: 0.02, 44: 0.1, 54: 0.0, 60: 0.0, 92: 1.0},
    {1: 0.0, 66: 0.0, 102: 1.0},
    {1: 0.0, 80: 0.0, 104: 0.55, 128: 0.0, 140: 0.0, 172: 1.0},
    {1: 0.0, 150: 0.0, 184: 1.0},
    {1: 0.0, 162: 0.0, 192: 0.45, 216: 0.0, 226: 0.03, 234: 0.0},
]


def paper_material():
    # Cream paper with fibres, yellowed edges and lines of "text" inside the
    # margins, faked from noise per line.
    shader = Shader("Paper")
    u, v = shader.uv()
    inside = [shader.math('GREATER_THAN', u, 0.1), shader.math('LESS_THAN', u, 0.88),
              shader.math('GREATER_THAN', v, 0.08), shader.math('LESS_THAN', v, 0.9)]
    lines = shader.math('MULTIPLY', v, 34.0)
    line = shader.math('FLOOR', lines)
    on_line = shader.math('LESS_THAN', shader.math('FRACT', lines), 0.5)
    words_at = shader.node("ShaderNodeCombineXYZ", {0: shader.math('MULTIPLY', u, 45.0), 1: shader.math('MULTIPLY', line, 7.3)}).outputs[0]
    words = shader.math('GREATER_THAN', shader.noise(words_at, 1.0, detail=1.0).outputs["Fac"], 0.42)
    letters = shader.math('GREATER_THAN', shader.math('SINE', shader.math('ADD', shader.math('MULTIPLY', u, 900.0), line)), -0.3)
    # Some lines end early, like the last line of a paragraph.
    per_line = shader.node("ShaderNodeCombineXYZ", {0: shader.math('MULTIPLY', line, 3.1)}).outputs[0]
    full = shader.math('GREATER_THAN', shader.noise(per_line, 1.0, detail=0.0).outputs["Fac"], 0.38)
    ends = shader.math('LESS_THAN', u, shader.math('ADD', 0.35, full))
    ink = on_line
    for mask in (*inside, words, letters, ends):
        ink = shader.math('MULTIPLY', ink, mask)
    fibres = shader.noise(shader.coords("Object"), 500.0, detail=6.0, roughness=0.7).outputs["Fac"]
    paper = shader.ramp(fibres, [(0.3, (0.76, 0.71, 0.6)), (0.7, (0.86, 0.81, 0.7))])
    edge = shader.math('MAXIMUM', shader.math('ABSOLUTE', shader.math('SUBTRACT', u, 0.5)), shader.math('ABSOLUTE', shader.math('SUBTRACT', v, 0.5)))
    aged = shader.node("ShaderNodeMapRange", {"Value": edge, 1: 0.4, 2: 0.5}).outputs[0]
    paper = shader.mix(shader.math('MULTIPLY', aged, 0.6), paper, (0.62, 0.5, 0.32))
    color = shader.mix(shader.math('MULTIPLY', ink, 0.92), paper, (0.03, 0.028, 0.025))
    roughness = shader.math('ADD', 0.75, shader.math('MULTIPLY', ink, -0.3))
    return shader.surface(color, roughness, shader.bump(fibres, 0.08, 0.001), translucency=0.15)


def page_edge_material():
    # The trimmed edges of the stacked pages: fine striations.
    shader = Shader("PageEdge")
    stripes = shader.noise(shader.coords("Object", (30.0, 30.0, 4000.0)), 1.0, detail=2.0).outputs["Fac"]
    color = shader.ramp(stripes, [(0.3, (0.55, 0.5, 0.4)), (0.7, (0.8, 0.75, 0.63))])
    return shader.surface(color, 0.8, shader.bump(stripes, 0.2, 0.0005))


def leather_material():
    # Pebbled oxblood leather, rubbed lighter where it has worn.
    shader = Shader("Leather")
    coords = shader.coords("Object")
    pebbles = shader.voronoi(coords, 450.0, 'SMOOTH_F1').outputs["Distance"]
    wear = shader.noise(coords, 12.0, detail=6.0, roughness=0.6).outputs["Fac"]
    color = shader.ramp(wear, [(0.35, (0.06, 0.008, 0.005)), (0.65, (0.16, 0.035, 0.02))])
    color = shader.mix(shader.math('MULTIPLY', pebbles, 0.5), color, (0.04, 0.008, 0.006))
    roughness = shader.math('ADD', 0.35, shader.math('MULTIPLY', pebbles, 0.3))
    return shader.surface(color, roughness, shader.bump(pebbles, 0.35, 0.0006), Sheen_Weight=0.3)


def ribbon_material():
    shader = Shader("Ribbon")
    weave = shader.noise(shader.coords("Object", (1.0, 1.0, 1.0)), 3000.0, detail=1.0).outputs["Fac"]
    return shader.surface((0.2, 0.006, 0.012), 0.35, shader.bump(weave, 0.1, 0.0002), Sheen_Weight=0.2)


def wood_material():
    # Oiled planks: wavering growth lines along the board, open pores and
    # a random offset per board so no two match.
    shader = Shader("Wood")
    offset = shader.math('MULTIPLY', shader.node("ShaderNodeObjectInfo").outputs["Random"], 50.0)
    coords = shader.node("ShaderNodeVectorMath", {0: shader.node("ShaderNodeTexCoord").outputs["Object"], 1: offset}, operation='ADD').outputs[0]
    sway = shader.noise(shader.node("ShaderNodeMapping", {"Vector": coords, "Scale": (0.6, 4.0, 4.0)}).outputs[0], 1.0, detail=2.0).outputs["Fac"]
    across = shader.node("ShaderNodeSeparateXYZ", {0: coords}).outputs[1]
    grain_at = shader.math('ADD', shader.math('MULTIPLY', across, 40.0), shader.math('MULTIPLY', sway, 12.0))
    lines = shader.math('POWER', shader.math('ABSOLUTE', shader.math('SINE', grain_at)), 6.0)
    pores = shader.noise(shader.node("ShaderNodeMapping", {"Vector": coords, "Scale": (3.0, 200.0, 200.0)}).outputs[0], 1.0, detail=3.0).outputs["Fac"]
    figure = shader.noise(coords, 6.0, detail=4.0).outputs["Fac"]
    color = shader.ramp(figure, [(0.35, (0.12, 0.055, 0.022)), (0.65, (0.24, 0.12, 0.05))])
    color = shader.mix(shader.math('MULTIPLY', lines, 0.6), color, (0.05, 0.022, 0.01))
    color = shader.mix(1.0, color, shader.ramp(pores, [(0.3, (0.8, 0.8, 0.8)), (0.7, (1.05, 1.05, 1.05))]), 'MULTIPLY')
    height = shader.math('ADD', shader.math('MULTIPLY', lines, 0.2), pores)
    roughness = shader.math('ADD', 0.35, shader.math('MULTIPLY', pores, 0.3))
    return shader.surface(color, roughness, shader.bump(height, 0.15, 0.001))


def lawn_material():
    shader = Shader("Lawn")
    patches = shader.noise(shader.coords("Object"), 1.5, detail=6.0).outputs["Fac"]
    color = shader.ramp(patches, [(0.35, (0.03, 0.06, 0.008)), (0.65, (0.09, 0.13, 0.02))])
    return shader.surface(color, 0.9)


def leaf_material():
    shader = Shader("AutumnLeaf")
    tint = shader.attribute("tint")
    u, _ = shader.uv()
    color = shader.ramp(tint, [(0.0, (0.35, 0.08, 0.01)), (0.5, (0.55, 0.25, 0.02)), (1.0, (0.4, 0.32, 0.05))])
    midrib = shader.math('LESS_THAN', shader.math('ABSOLUTE', shader.math('SUBTRACT', u, 0.5)), 0.04)
    color = shader.mix(shader.math('MULTIPLY', midrib, 0.5), color, (0.6, 0.45, 0.2))
    spots = shader.noise(shader.coords("Object"), 300.0, detail=4.0).outputs["Fac"]
    color = shader.mix(shader.math('GREATER_THAN', spots, 0.65), color, (0.12, 0.05, 0.02))
    return shader.surface(color, 0.55, translucency=0.3)


def rest_angle(s):
    # The slope of the page surface s metres from the spine: rising steeply out
    # of the gutter, then sagging a little towards the edge.
    return 0.8 * math.exp(-s / 0.012) - 0.04 * s / PAGE_WIDTH


def page_profile(flip, count, lift=0.0):
    # (x, z) points across a page: flip turns it over the spine, the free edge
    # lagging behind in a curl while it is in the air.
    theta = math.pi * flip
    curl = 1.2 * math.sin(math.pi * flip)
    step = PAGE_WIDTH / count
    x, z = 0.0, HINGE + lift
    points = [(x, z)]
    for i in range(count):
        s = (i + 0.5) * step
        angle = theta + rest_angle(s) * math.cos(theta) - curl * (s / PAGE_WIDTH) ** 1.3
        x += math.cos(angle) * step
        z += math.sin(angle) * step
        points.append((x, z))
    return points


def add_page_block(paper, edge, side):
    # The stack of pages on one side, shaped to the curve of its top page.
    profile = [(side * x, z) for x, z in page_profile(0.0, 30)]
    half = PAGE_HEIGHT / 2
    n = len(profile)
    verts = [(x, y, z) for y in (-half, half) for x, z in profile]
    verts += [(x, y, BOARD) for y in (-half, half) for x, _ in profile]
    top, bottom = 0, 2 * n
    faces, uvs, materials = [], [], []
    for i in range(n - 1):
        faces.append([top + i, top + i + 1, top + n + i + 1, top + n + i])
        uvs.append([(i / (n - 1), 0), ((i + 1) / (n - 1), 0), ((i + 1) / (n - 1), 1), (i / (n - 1), 1)])
        materials.append(0)
        # Head and tail of the stack.
        faces.append([bottom + i + 1, bottom + i, top + i, top + i + 1])
        faces.append([top + n + i + 1, top + n + i, bottom + n + i, bottom + n + i + 1])
        uvs += [[(0, 0)] * 4] * 2
        materials += [1, 1]
    # The fore-edge.
    faces.append([top + n - 1, bottom + n - 1, bottom + 2 * n - 1, top + 2 * n - 1])
    uvs.append([(0, 0)] * 4)
    materials.append(1)
    if side < 0:
        # Mirrored, so turn the faces back outwards.
        faces = [face[::-1] for face in faces]
        uvs = [uv[::-1] for uv in uvs]
    builder = MeshBuilder()
    builder.add(verts, faces, uvs, material=materials)
    block = builder.build(f"Pages.{'R' if side > 0 else 'L'}", [paper, edge])
    block.data.set_sharp_from_angle(angle=math.radians(40))
    return block


def add_cover(leather):
    margin = 0.005
    half_width = PAGE_WIDTH + margin
    half_height = PAGE_HEIGHT / 2 + margin
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, BOARD / 2))
    cover = bpy.context.active_object
    cover.name = "Cover"
    cover.scale = (2 * half_width, 2 * half_height, BOARD)
    bpy.ops.object.transform_apply(scale=True)
    bevel = cover.modifiers.new(name="Bevel", type='BEVEL')
    bevel.width = 0.0012
    bevel.segments = 3
    cover.data.materials.append(leather)
    bpy.ops.object.shade_smooth()
    return cover


def add_flip_page(index, paper, mover):
    # A loose page that the wind turns: shape keys hold it at every stage of
    # the turn, blended by its "flip" property.
    nx, ny = 30, 6
    lift = (len(FLIPS) - index) * LEAF_GAP

    def shape(flip):
        # The page lifts from the top of the right stack to the top of the left.
        landing = (index + 1) * LEAF_GAP
        profile = page_profile(flip, nx, lift + (landing - lift) * flip)
        return [(profile[i][0], (j / ny - 0.5) * PAGE_HEIGHT, profile[i][1]) for j in range(ny + 1) for i in range(nx + 1)]

    builder = MeshBuilder(groups=("wind",))
    verts = shape(0.0)
    faces, uvs = [], []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append([a, a + 1, a + nx + 2, a + nx + 1])
            uvs.append([(i / nx, j / ny), ((i + 1) / nx, j / ny), ((i + 1) / nx, (j + 1) / ny), (i / nx, (j + 1) / ny)])
    builder.add(verts, faces, uvs, wind=[(i / nx) ** 2 for j in range(ny + 1) for i in range(nx + 1)])
    page = builder.build(f"Page.{index}", [paper])
    page["flip"] = 0.0
    page.shape_key_add(name="Basis")
    for k in range(1, STAGES + 1):
        key = page.shape_key_add(name=f"Flip.{k:02d}")
        key.data.foreach_set("co", [c for v in shape(k / STAGES) for c in v])
        driver = key.driver_add("value").driver
        variable = driver.variables.new()
        variable.name = "flip"
        variable.targets[0].id = page
        variable.targets[0].data_path = '["flip"]'
        driver.expression = f"max(0, 1 - abs(flip * {STAGES} - {k}))"
    # Flutters only while airborne, so it never digs into the stacks.
    flutter = add_displace(page, mover, size=0.08, strength=0.0, direction='Z')
    driver = flutter.driver_add("strength").driver
    variable = driver.variables.new()
    variable.name = "flip"
    variable.targets[0].id = page
    variable.targets[0].data_path = '["flip"]'
    driver.expression = "0.03 * sin(pi * min(max(flip, 0), 1))"
    for frame, flip in FLIPS[index].items():
        page["flip"] = flip
        page.keyframe_insert(data_path='["flip"]', frame=frame)
    return page


def add_ribbon(mover):
    # A satin bookmark coming out of the gutter at the tail of the book and
    # trailing across the table, its loose end lifting in the gusts.
    half = PAGE_HEIGHT / 2
    path = [Vector((0.0, -half + 0.03, HINGE + 0.002)), Vector((0.004, -half, HINGE)), Vector((0.01, -half - 0.012, BOARD)),
            Vector((0.02, -half - 0.03, 0.0006))]
    for k in range(1, 12):
        path.append(path[-1] + Vector((0.012 * math.sin(k * 0.5), -0.012, 0.0)))
    builder = MeshBuilder(groups=("wind",))
    verts, faces, weights, uvs = [], [], [], []
    for k, point in enumerate(path):
        heading = (path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]).normalized()
        side = heading.cross(Vector((0, 0, 1))).normalized() * 0.0035
        verts += [tuple(point - side), tuple(point + side)]
        weights += [max(k - 3, 0) / (len(path) - 4)] * 2
    for k in range(len(path) - 1):
        faces.append([2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2])
        uvs.append([(0, k), (1, k), (1, k + 1), (0, k + 1)])
    builder.add(verts, faces, uvs, wind=[w ** 1.5 for w in weights])
    ribbon = builder.build("Ribbon", [ribbon_material()])
    add_displace(ribbon, mover, size=0.05, strength=0.05, direction='Z', mid_level=0.3)
    add_displace(ribbon, mover, size=0.08, strength=0.03, direction='X')
    return ribbon


def add_table(wood):
    boards, width, gap, length = 5, 0.145, 0.005, 1.6
    for b in range(boards):
        y = (b - (boards - 1) / 2) * (width + gap)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, -0.015))
        board = bpy.context.active_object
        board.name = f"Board.{b}"
        board.scale = (length, width, 0.03)
        bpy.ops.object.transform_apply(scale=True)
        bevel = board.modifiers.new(name="Bevel", type='BEVEL')
        bevel.width = 0.003
        bevel.segments = 2
        board.data.materials.append(wood)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.75))
    bpy.context.active_object.name = "Lawn"
    bpy.context.active_object.data.materials.append(lawn_material())


def add_blown_leaf(rng, index, material, y, start, speed):
    # A dry leaf skittering across the table in hops, tumbling as it goes.
    builder = MeshBuilder(attributes=("tint",))
    add_leaf(builder, (-0.02, 0, 0), (1, 0, 0), (0, 0, 1), 0.05, 0.03, rows=5, tint=rng.random())
    leaf = builder.build(f"Leaf.{index}", [material])
    end = bpy.context.scene.frame_end
    phase = rng.uniform(0, math.pi)
    for frame in range(start, end + 1, 3):
        t = (frame - start) / 24
        x = -0.75 + speed * t + 0.02 * math.sin(3 * t + phase)
        hop = abs(math.sin(2.2 * t + phase)) ** 3
        leaf.location = (x, y + 0.03 * math.sin(1.3 * t + phase), 0.002 + 0.05 * hop)
        leaf.rotation_euler = (2.5 * hop * math.sin(5 * t), 1.5 * hop * math.cos(4 * t), 1.2 * t + phase)
        leaf.keyframe_insert(data_path="location", frame=frame)
        leaf.keyframe_insert(data_path="rotation_euler", frame=frame)
    return leaf


def basicbook():
    setup_stage(sun_elevation=35, sun_rotation=-20, sun_energy=3.5, sky_strength=0.1)
    rng = random.Random(5)
    paper = paper_material()
    edge = page_edge_material()
    add_table(wood_material())
    add_cover(leather_material())
    add_page_block(paper, edge, 1)
    add_page_block(paper, edge, -1)
    flutter = add_mover("Flutter", (0.02, 0.0, 0.015))
    for index in range(len(FLIPS)):
        add_flip_page(index, paper, flutter)
    add_ribbon(add_mover("Gusts", (0.03, 0.01, 0.02)))
    material = leaf_material()
    for index, (y, start, speed) in enumerate([(-0.22, 1, 0.16), (0.2, 40, 0.2), (-0.3, 110, 0.24)]):
        add_blown_leaf(rng, index, material, y, start, speed)
    camera, _ = add_camera((0.34, -0.46, 0.34), (0.0, -0.01, 0.0), lens=50, fstop=4.0)
    end = bpy.context.scene.frame_end
    keyframes(camera, "location", {1: (0.34, -0.46, 0.34), end: (0.12, -0.55, 0.3)})
