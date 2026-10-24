"""Build and render the fluffy puppy in Blender.

Modelled on the tri-colour hound puppy in the reference photo: black saddle,
tan face and legs, white blaze, chest and paws, tan eyebrow dots, floppy ears.

The body and head are sculpted from metaballs (smoothly blended shapes) and
converted to meshes, then covered in soft particle fur shaded with the
Principled Hair BSDF. Markings are painted procedurally in object space, so the
same colour masks drive both the skin and the fur. Eyes and nose get their own
procedural textures (iris and pupil, bumpy nose leather).

Run headless, one mood per invocation:

    Blender --background --python tools/blender/dog.py -- --mood awake --out build/frames/awake
    Blender --background --python tools/blender/dog.py -- --mood awake --still build/awake.png

Moods: awake (head tilt, blink, tail wag), happy (tongue out, bounce, fast wag),
sleepy (lying down, slow breathing, rising Zzz). Every animation is FRAMES long
and loops seamlessly.
"""

import argparse
import math
import sys

import bpy
from mathutils import Euler, Vector

FRAMES = 30
FPS = 10

# Coat colours, linear RGB
BLACK = (0.018, 0.015, 0.014)
TAN = (0.33, 0.14, 0.05)
WHITE = (0.78, 0.74, 0.68)
DARK_TAN = (0.10, 0.04, 0.015)
NOSE = (0.012, 0.010, 0.010)
IRIS = (0.05, 0.020, 0.008)
TONGUE = (0.80, 0.25, 0.30)
STONE = (0.10, 0.13, 0.17)
BALL = (0.50, 0.70, 0.05)
ZZZ = (0.04, 0.22, 1.0)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--mood", choices=["awake", "happy", "sleepy"], default="awake")
    p.add_argument("--out", help="directory for the PNG frame sequence")
    p.add_argument("--still", help="render only frame 1 to this PNG")
    p.add_argument("--size", type=int, default=480)
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--no-fur", action="store_true", help="skip fur for fast shape drafts")
    p.add_argument("--blend", help="also save the .blend file here")
    return p.parse_args(argv)


# --- materials -------------------------------------------------------------

def _node(nodes, kind, **inputs):
    n = nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def coat_color(nodes, links, base, patches):
    """Build a colour from a base plus ellipsoid patches in object space.
    Each patch is (colour, centre, radii), painted in order with a noisy edge
    so it reads as fur markings. Returns the colour output socket."""
    coords = nodes.new("ShaderNodeTexCoord")
    noise = _node(nodes, "ShaderNodeTexNoise", Scale=14.0, Detail=5.0)
    links.new(coords.outputs["Object"], noise.inputs["Vector"])

    color = _node(nodes, "ShaderNodeRGB")
    color.outputs[0].default_value = (*base, 1)
    current = color.outputs[0]
    for patch_color, centre, radii in patches:
        sub = nodes.new("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        sub.inputs[1].default_value = centre
        links.new(coords.outputs["Object"], sub.inputs[0])
        div = nodes.new("ShaderNodeVectorMath")
        div.operation = "DIVIDE"
        div.inputs[1].default_value = radii
        links.new(sub.outputs[0], div.inputs[0])
        length = nodes.new("ShaderNodeVectorMath")
        length.operation = "LENGTH"
        links.new(div.outputs[0], length.inputs[0])
        wobble = nodes.new("ShaderNodeMath")
        wobble.operation = "MULTIPLY_ADD"
        wobble.inputs[1].default_value = 0.25
        links.new(noise.outputs["Fac"], wobble.inputs[0])
        links.new(length.outputs["Value"], wobble.inputs[2])
        mask = nodes.new("ShaderNodeMapRange")
        mask.interpolation_type = "SMOOTHSTEP"
        mask.inputs["From Min"].default_value = 1.15
        mask.inputs["From Max"].default_value = 0.95
        links.new(wobble.outputs[0], mask.inputs["Value"])
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["B"].default_value = (*patch_color, 1)
        links.new(mask.outputs["Result"], mix.inputs["Factor"])
        links.new(current, mix.inputs["A"])
        current = mix.outputs["Result"]

    # Gentle tonal variation through the coat
    variation = _node(nodes, "ShaderNodeTexNoise", Scale=40.0, Detail=3.0)
    links.new(coords.outputs["Object"], variation.inputs["Vector"])
    vary = nodes.new("ShaderNodeMapRange")
    vary.inputs["To Min"].default_value = 0.85
    vary.inputs["To Max"].default_value = 1.12
    links.new(variation.outputs["Fac"], vary.inputs["Value"])
    shade = nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    shade.inputs["Factor"].default_value = 1.0
    links.new(current, shade.inputs["A"])
    links.new(vary.outputs["Result"], shade.inputs["B"])
    return shade.outputs["Result"]


def coat_materials(name, base, patches=()):
    """A skin material and a matching fur material sharing the same markings."""
    skin = bpy.data.materials.new(name)
    nodes, links = skin.node_tree.nodes, skin.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    links.new(coat_color(nodes, links, base, patches), bsdf.inputs["Base Color"])

    fur = bpy.data.materials.new(name + "_fur")
    nodes, links = fur.node_tree.nodes, fur.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    hair = nodes.new("ShaderNodeBsdfHairPrincipled")
    hair.parametrization = "COLOR"
    hair.inputs["Roughness"].default_value = 0.5
    hair.inputs["Radial Roughness"].default_value = 0.7
    hair.inputs["Coat"].default_value = 0.0
    # Slightly lighter towards the tips for a soft, fluffy look
    info = nodes.new("ShaderNodeHairInfo")
    tip = nodes.new("ShaderNodeMath")
    tip.operation = "MULTIPLY_ADD"
    tip.inputs[1].default_value = 0.3
    tip.inputs[2].default_value = 1.0
    links.new(info.outputs["Intercept"], tip.inputs[0])
    lighten = nodes.new("ShaderNodeMix")
    lighten.data_type = "RGBA"
    lighten.blend_type = "MULTIPLY"
    lighten.inputs["Factor"].default_value = 1.0
    links.new(coat_color(nodes, links, base, patches), lighten.inputs["A"])
    links.new(tip.outputs[0], lighten.inputs["B"])
    links.new(lighten.outputs["Result"], hair.inputs["Color"])
    links.new(hair.outputs["BSDF"], out.inputs["Surface"])
    return skin, fur


def glossy_material(name, color, roughness=0.15, coat=1.0):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Coat Weight"].default_value = coat
    return mat


def nose_material():
    """Damp, pebbly nose leather from a Voronoi bump."""
    mat = glossy_material("nose", NOSE, 0.35, 0.5)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    cells = _node(nodes, "ShaderNodeTexVoronoi", Scale=90.0)
    links.new(coords.outputs["Object"], cells.inputs["Vector"])
    bump = _node(nodes, "ShaderNodeBump", Strength=0.35, Distance=0.002)
    links.new(cells.outputs["Distance"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], nodes["Principled BSDF"].inputs["Normal"])
    return mat


def eye_material(radius):
    """Wet eye with a procedural iris: black pupil, streaky brown iris and a
    dark outer ring, measured from the eye's centre in its local XZ plane."""
    mat = glossy_material("eye", IRIS, 0.03, 1.0)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new("ShaderNodeTexCoord")
    xz = nodes.new("ShaderNodeVectorMath")
    xz.operation = "MULTIPLY"
    xz.inputs[1].default_value = (1 / radius, 0, 1 / radius)
    links.new(coords.outputs["Object"], xz.inputs[0])
    dist = nodes.new("ShaderNodeVectorMath")
    dist.operation = "LENGTH"
    links.new(xz.outputs[0], dist.inputs[0])
    streaks = _node(nodes, "ShaderNodeTexNoise", Scale=30.0, Detail=2.0)
    links.new(coords.outputs["Object"], streaks.inputs["Vector"])
    warp = nodes.new("ShaderNodeMath")
    warp.operation = "MULTIPLY_ADD"
    warp.inputs[1].default_value = 0.08
    links.new(streaks.outputs["Fac"], warp.inputs[0])
    links.new(dist.outputs["Value"], warp.inputs[2])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.42, (0.003, 0.002, 0.002, 1)
    els[1].position, els[1].color = 0.95, (0.01, 0.005, 0.003, 1)
    mid = els.new(0.50)
    mid.color = (*IRIS, 1)
    edge = els.new(0.80)
    edge.color = (IRIS[0] * 1.6, IRIS[1] * 1.6, IRIS[2] * 1.6, 1)
    links.new(warp.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    return mat


def emissive_material(name, color, strength=0.8):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Emission Color"].default_value = (*color, 1)
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


# --- geometry --------------------------------------------------------------

def link(obj, parent=None):
    bpy.context.collection.objects.link(obj)
    if parent:
        set_parent(obj, parent)
    return obj


def empty(name, loc, parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.location = loc
    return link(obj, parent)


def set_parent(child, parent):
    bpy.context.view_layer.update()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def sculpt(name, elements, mats, parent=None, fur=None, resolution=0.012):
    """Melt metaball ellipsoids into one smooth mesh. Each element is
    (centre, semi_axes) or (centre, semi_axes, rotation_degrees), in world
    space with the object at the origin, so object coordinates (used by the
    markings) are world coordinates of the rest pose."""
    mb = bpy.data.metaballs.new(name)
    mb.resolution = mb.render_resolution = resolution
    mb.threshold = 0.6
    for el in elements:
        centre, semi = el[0], el[1]
        rot = el[2] if len(el) > 2 else (0, 0, 0)
        e = mb.elements.new()
        e.type = "ELLIPSOID"
        e.co = centre
        e.radius = 1.0
        # Measured: an ellipsoid element's surface sits at ~0.57 x its size
        e.size_x, e.size_y, e.size_z = (s / 0.57 for s in semi)
        e.rotation = Euler([math.radians(a) for a in rot]).to_quaternion()
    obj = bpy.data.objects.new(name, mb)
    bpy.context.collection.objects.link(obj)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.shade_smooth()
    smooth = obj.modifiers.new("smooth", "SMOOTH")
    smooth.iterations = 4
    bpy.ops.object.modifier_apply(modifier="smooth")
    for m in mats:
        obj.data.materials.append(m)
    if parent:
        set_parent(obj, parent)
    if fur and not ARGS.no_fur:
        add_fur(obj, mats[1], *fur)
    return obj


def blob(name, loc, scale, mat, parent=None, rot=(0, 0, 0), segments=48):
    """A plain ellipsoid with its scale applied (for eyes, tongue, props)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=segments // 2, radius=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler = [math.radians(a) for a in rot]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(mat)
    if parent:
        set_parent(obj, parent)
    return obj


def surface_y(obj, x, z):
    """Where a ray fired from in front of the dog along +Y first hits obj."""
    bpy.context.view_layer.update()
    inv = obj.matrix_world.inverted()
    origin = inv @ Vector((x, -5.0, z))
    direction = (inv.to_3x3() @ Vector((0, 1, 0))).normalized()
    hit, loc, _, _ = obj.ray_cast(origin, direction)
    return (obj.matrix_world @ loc).y if hit else None


def add_fur(obj, hair_mat, length, density, droop=0.4):
    """Soft fur from a hair particle system, combed downward by `droop`.
    density is parent strands per square metre; children fill in at render."""
    area = sum(p.area for p in obj.data.polygons)
    mod = obj.modifiers.new("fur", "PARTICLE_SYSTEM")
    s = mod.particle_system.settings
    s.type = "HAIR"
    s.count = max(300, int(area * density))
    # With advanced hair, strand length and direction come from the emission
    # velocity: out along the normal, pulled down a little like real fur
    s.use_advanced_hair = True
    s.normal_factor = length
    s.object_align_factor = (0, 0, -droop * length)
    s.factor_random = length * 0.25
    s.hair_length = length
    s.hair_step = 5
    s.render_step = 3
    s.display_step = 2
    s.child_type = "INTERPOLATED"
    s.child_percent = 2
    # Kept modest: the dense version swaps on an 8 GB Mac and looks the same at watch size
    s.rendered_child_count = 22
    s.child_length = 1.0
    s.child_length_threshold = 0.3
    s.clump_factor = 0.12
    s.clump_shape = 0.3
    s.roughness_1 = length * 0.25
    s.roughness_2 = length * 0.1
    s.roughness_endpoint = length * 0.15
    s.root_radius = 1.0
    s.tip_radius = 0.05
    s.radius_scale = 0.0015
    s.material_slot = hair_mat.name


# --- the dog ---------------------------------------------------------------

def build_dog(pose):
    """Sculpt the puppy. The head is modelled around a pivot at (0, -0.05, 0.95)
    and then scaled up and moved onto the neck; the sleepy pose lies the body
    down and rests the head on the front paws."""
    lying = pose == "lying"
    root = empty("root", (0, 0, 0))
    rig = {"root": root}

    if lying:
        body = [
            ((0, 0.20, 0.20), (0.21, 0.32, 0.17)),
            ((0, -0.04, 0.24), (0.17, 0.14, 0.15)),
            ((0, -0.10, 0.32), (0.13, 0.13, 0.13)),
        ]
        for side in (-1, 1):
            body += [
                ((side * 0.15, 0.36, 0.15), (0.12, 0.16, 0.12)),
                ((side * 0.10, -0.18, 0.07), (0.06, 0.17, 0.06)),
                ((side * 0.10, -0.38, 0.05), (0.07, 0.09, 0.05)),
                ((side * 0.21, 0.17, 0.045), (0.065, 0.10, 0.045)),
            ]
        body_patches = [
            (WHITE, (0, -0.16, 0.18), (0.13, 0.16, 0.12)),
            (TAN, (-0.10, -0.24, 0.07), (0.08, 0.14, 0.08)),
            (TAN, (0.10, -0.24, 0.07), (0.08, 0.14, 0.08)),
            (WHITE, (-0.10, -0.38, 0.05), (0.09, 0.11, 0.08)),
            (WHITE, (0.10, -0.38, 0.05), (0.09, 0.11, 0.08)),
            (WHITE, (-0.21, 0.17, 0.045), (0.08, 0.12, 0.07)),
            (WHITE, (0.21, 0.17, 0.045), (0.08, 0.12, 0.07)),
            (TAN, (-0.17, 0.40, 0.10), (0.10, 0.12, 0.10)),
            (TAN, (0.17, 0.40, 0.10), (0.10, 0.12, 0.10)),
        ]
    else:
        body = [
            ((0, 0.04, 0.42), (0.19, 0.19, 0.25), (-6, 0, 0)),
            ((0, 0.08, 0.22), (0.20, 0.21, 0.14)),
            ((0, -0.03, 0.64), (0.13, 0.13, 0.13)),
        ]
        for side in (-1, 1):
            body += [
                ((side * 0.15, 0.10, 0.16), (0.12, 0.16, 0.13)),
                ((side * 0.095, -0.12, 0.21), (0.06, 0.06, 0.18)),
                ((side * 0.095, -0.17, 0.05), (0.07, 0.09, 0.05)),
                ((side * 0.21, -0.05, 0.045), (0.065, 0.10, 0.045)),
            ]
        body_patches = [
            (WHITE, (0, -0.17, 0.42), (0.12, 0.12, 0.30)),
            (WHITE, (0, -0.12, 0.64), (0.09, 0.07, 0.13)),
            (TAN, (-0.095, -0.16, 0.20), (0.10, 0.12, 0.17)),
            (TAN, (0.095, -0.16, 0.20), (0.10, 0.12, 0.17)),
            (WHITE, (-0.095, -0.17, 0.06), (0.09, 0.11, 0.09)),
            (WHITE, (0.095, -0.17, 0.06), (0.09, 0.11, 0.09)),
            (WHITE, (-0.21, -0.05, 0.045), (0.08, 0.12, 0.07)),
            (WHITE, (0.21, -0.05, 0.045), (0.08, 0.12, 0.07)),
            (TAN, (-0.17, 0.0, 0.12), (0.09, 0.10, 0.09)),
            (TAN, (0.17, 0.0, 0.12), (0.09, 0.10, 0.09)),
        ]
    rig["torso"] = sculpt("body", body, coat_materials("body", BLACK, body_patches), root,
                          fur=(0.045, 7000, 0.5))

    # Tail: a short blended chain curling out to the dog's left
    tail_root = empty("tail_root", (0.12, 0.50, 0.15) if lying else (0.12, 0.22, 0.10), root)
    rig["tail"] = tail_root
    base = Vector(tail_root.location)
    tail = [(tuple(base + Vector(d)), (0.045, 0.045, 0.06)) for d in
            [(0.0, 0.0, 0.0), (0.08, 0.03, 0.03), (0.16, 0.0, 0.09), (0.22, -0.05, 0.17), (0.25, -0.09, 0.24)]]
    tip = tuple(base + Vector((0.25, -0.09, 0.24)))
    sculpt("tail", tail, coat_materials("tail", BLACK, [(WHITE, tip, (0.06, 0.06, 0.08))]), tail_root,
           fur=(0.04, 9000, 0.2))

    # Head
    head_pivot = empty("head_pivot", (0, -0.05, 0.95), root)
    rig["head"] = head_pivot
    head = [
        ((0, -0.07, 1.17), (0.23, 0.22, 0.21)),
        ((0, -0.19, 1.20), (0.16, 0.10, 0.10)),
        ((-0.12, -0.19, 1.07), (0.10, 0.10, 0.09)),
        ((0.12, -0.19, 1.07), (0.10, 0.10, 0.09)),
        ((0, -0.29, 1.05), (0.11, 0.11, 0.08)),
        ((-0.055, -0.30, 1.00), (0.065, 0.07, 0.055)),
        ((0.055, -0.30, 1.00), (0.065, 0.07, 0.055)),
        ((0, -0.24, 0.97), (0.07, 0.07, 0.05)),
    ]
    head_patches = [
        (BLACK, (0, 0.02, 1.36), (0.30, 0.30, 0.17)),
        (BLACK, (0, 0.14, 1.18), (0.28, 0.12, 0.24)),
        (TAN, (-0.08, -0.24, 1.30), (0.04, 0.06, 0.028)),
        (TAN, (0.08, -0.24, 1.30), (0.04, 0.06, 0.028)),
        (WHITE, (0, -0.28, 1.20), (0.04, 0.12, 0.17)),
        (WHITE, (0, -0.35, 1.02), (0.13, 0.12, 0.10)),
        (WHITE, (0, -0.25, 0.96), (0.08, 0.08, 0.06)),
    ]
    head_mesh = sculpt("head", head, coat_materials("head", TAN, head_patches), head_pivot,
                       fur=(0.02, 12000, 0.3))

    # Nose and eyes sit on the sculpted surface, found by ray casting
    nose_z = 1.075
    nose_y = (surface_y(head_mesh, 0, nose_z) or -0.40) - 0.01
    nose = [((0, nose_y, nose_z), (0.06, 0.04, 0.04)),
            ((-0.022, nose_y - 0.008, nose_z - 0.006), (0.035, 0.03, 0.03)),
            ((0.022, nose_y - 0.008, nose_z - 0.006), (0.035, 0.03, 0.03))]
    sculpt("nose", nose, [nose_material()], head_pivot, resolution=0.006)

    eye_r = 0.055
    eye_mat = eye_material(eye_r)
    sparkle = emissive_material("sparkle", (1, 1, 1), 2.0)
    rig["eyes"] = []
    for side in (-1, 1):
        ex, ez = side * 0.10, 1.165
        ey = (surface_y(head_mesh, ex, ez) or -0.30) + eye_r * 0.15
        eye = blob(f"eye{side}", (ex, ey, ez), (eye_r, eye_r * 0.8, eye_r), eye_mat, head_pivot)
        blob(f"sparkle{side}", (ex - 0.016, ey - eye_r * 0.78, ez + 0.018), (0.008, 0.004, 0.008), sparkle, eye, segments=16)
        rig["eyes"].append(eye)

    # Long, soft hound ears: a narrow top melting into a wide rounded flap
    rig["ears"] = []
    for side in (-1, 1):
        px, pz = side * 0.19, 1.27
        pivot = empty(f"ear_pivot{side}", (px, -0.05, pz), head_pivot)
        x = px + side * 0.04
        ear = [((x, -0.04, pz - 0.04), (0.06, 0.03, 0.07)),
               ((x + side * 0.03, -0.05, pz - 0.18), (0.10, 0.03, 0.13)),
               ((x + side * 0.05, -0.06, pz - 0.30), (0.09, 0.03, 0.09))]
        ear = [(c, s, (0, side * -10, 0)) for c, s in ear]
        tip = (x + side * 0.05, -0.06, pz - 0.36)
        sculpt(f"ear{side}", ear, coat_materials(f"ear{side}", TAN, [(DARK_TAN, tip, (0.12, 0.08, 0.09))]),
               pivot, fur=(0.022, 12000, 0.6))
        rig["ears"].append(pivot)

    rig["tongue"] = blob("tongue", (0, -0.36, 0.95), (0.04, 0.025, 0.055), glossy_material("tongue", TONGUE, 0.3, 0.3), head_pivot)

    head_pivot.scale = (1.42,) * 3
    if lying:
        head_pivot.location = (0, -0.28, 0.22)
        head_pivot.rotation_euler = (math.radians(14), math.radians(-14), math.radians(12))
        root.rotation_euler = (0, 0, math.radians(-38))
        root.location = (0.14, 0.18, 0)
    else:
        head_pivot.location = (0, -0.05, 0.70)
        head_pivot.rotation_euler = (0, math.radians(6), 0)
    return rig


def build_ground():
    stone_mat = glossy_material("stone", STONE, 0.7, 0.0)
    for i, (x, y, s) in enumerate([(-0.36, -0.26, 0.09), (-0.22, -0.38, 0.065), (0.40, -0.20, 0.06)]):
        blob(f"stone{i}", (x, y, s * 0.3), (s * 1.3, s, s * 0.6), stone_mat, segments=24)
    skin, fur = coat_materials("ball", BALL)
    ball = sculpt("ball", [((0.33, -0.40, 0.085), (0.085, 0.085, 0.085))], (skin, fur), resolution=0.01)
    if not ARGS.no_fur:
        add_fur(ball, fur, 0.008, 40000, 0.0)


def build_zzz():
    mat = emissive_material("zzz", ZZZ)
    letters = []
    for i in range(3):
        bpy.ops.object.text_add(location=(0, 0, 0))
        z = bpy.context.active_object
        z.data.body = "Z"
        z.data.extrude = 0.02
        z.data.bevel_depth = 0.006
        z.data.align_x = "CENTER"
        z.data.materials.append(mat)
        z.rotation_euler = (math.radians(80), 0, math.radians(10))
        letters.append(z)
    return letters


# --- scene -----------------------------------------------------------------

def setup_scene(size, samples):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    # Skip per-scene kernel specialisation: it recompiles for minutes whenever
    # the shaders change, which costs far more than it saves on short renders
    if hasattr(prefs, "kernel_optimization_level"):
        prefs.kernel_optimization_level = "OFF"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Khronos PBR Neutral"
    scene.frame_start, scene.frame_end = 1, FRAMES
    scene.render.fps = FPS

    world = bpy.data.worlds.new("world")
    scene.world = world
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.06, 0.06, 0.07, 1)

    cam_data = bpy.data.cameras.new("camera")
    cam_data.lens = 70
    cam = bpy.data.objects.new("camera", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.4, -3.8, 1.3)
    target = Vector((0.0, -0.10, 0.72))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    def area_light(name, loc, energy, size, color=(1, 1, 1)):
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.size, data.color = energy, size, color
        light = bpy.data.objects.new(name, data)
        light.location = loc
        light.rotation_euler = (Vector((0, 0, 0.7)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(light)

    # Soft warm key and fill, with back lights to make the fur edges glow
    area_light("key", (-2.0, -3.2, 3.0), 1000, 4.0, (1.0, 0.92, 0.82))
    area_light("fill", (3.0, -2.5, 1.2), 350, 4.0, (0.88, 0.92, 1.0))
    area_light("rim", (1.6, 2.8, 2.6), 500, 2.5, (1.0, 0.95, 0.9))
    area_light("rim2", (-1.8, 2.6, 2.2), 300, 2.5, (0.9, 0.93, 1.0))


# --- animation -------------------------------------------------------------

def key(obj, path, frame, value):
    getattr(obj, path)[:] = value
    obj.keyframe_insert(data_path=path, frame=frame)


def wave(frame, cycles, phase=0.0):
    return math.sin(2 * math.pi * (cycles * (frame - 1) / FRAMES + phase))


def animate(rig, mood, zzz):
    torso = rig["torso"]
    base_scale = tuple(torso.scale)
    head_rest = tuple(rig["head"].rotation_euler)
    for f in range(1, FRAMES + 1):
        breath = 0.010 * wave(f, 1 if mood == "sleepy" else 2)
        key(torso, "scale", f, (base_scale[0] * (1 + breath), base_scale[1] * (1 + breath), base_scale[2] * (1 + breath * 0.5)))

        if mood == "awake":
            tilt = math.radians(14) * max(0.0, wave(f, 1, 0.0)) ** 1.5
            wag = math.radians(28) * wave(f, 3)
            blink = 0.1 if f in (19, 20) else 1.0
        elif mood == "happy":
            tilt = math.radians(5) * wave(f, 2)
            wag = math.radians(40) * wave(f, 5)
            blink = 0.7
            key(rig["root"], "location", f, (0, 0, 0.025 * abs(wave(f, 2))))
        else:
            tilt = 0.0
            wag = math.radians(6) * wave(f, 1)
            blink = 0.06

        key(rig["head"], "rotation_euler", f, (head_rest[0], head_rest[1] + tilt, head_rest[2]))
        key(rig["tail"], "rotation_euler", f, (0, 0, wag))
        for eye in rig["eyes"]:
            key(eye, "scale", f, (1, 1, blink))
        for i, ear in enumerate(rig["ears"]):
            # Ears lag the head a little and flop the other way
            flop = -0.6 * tilt + (math.radians(8) * max(0.0, wave(f, 1, 0.3)) if mood == "sleepy" and i == 1 else 0)
            key(ear, "rotation_euler", f, (0, flop, 0))

        if mood == "sleepy":
            for i, z in enumerate(zzz):
                t = ((f - 1) / FRAMES + i / 3) % 1.0
                key(z, "location", f, (0.12 + 0.20 * t, -0.50, 0.78 + 0.45 * t))
                s = 0.10 + 0.10 * t
                fade = min(1.0, t * 4, (1 - t) * 4)
                key(z, "scale", f, (s * fade, s * fade, s * fade))

    rig["tongue"].hide_render = mood != "happy"
    for z in zzz:
        z.hide_render = mood != "sleepy"


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Every frame is keyed, so linear keys reproduce the curves exactly
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    setup_scene(ARGS.size, ARGS.samples)
    rig = build_dog("lying" if ARGS.mood == "sleepy" else "sitting")
    build_ground()
    zzz = build_zzz()
    animate(rig, ARGS.mood, zzz)
    scene = bpy.context.scene
    if ARGS.blend:
        bpy.ops.wm.save_as_mainfile(filepath=ARGS.blend)
    if ARGS.still:
        scene.frame_set(1)
        scene.render.filepath = ARGS.still
        bpy.ops.render.render(write_still=True)
    elif ARGS.out:
        scene.render.filepath = ARGS.out.rstrip("/") + "/"
        bpy.ops.render.render(animation=True)


ARGS = parse_args()
main()
