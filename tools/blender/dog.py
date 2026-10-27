"""Build and render the dogs in Blender.

    puppy  tri-colour hound puppy: black saddle, tan face and legs, white blaze,
           chest and paws, tan eyebrow dots, floppy ears
    nova   golden long-haired dachshund with silky feathered ears and tail
    ozzie  red cattle dog mix: ginger with white markings, one pricked ear and
           one folded, bushy banded tail

The body and head are sculpted from metaballs (smoothly blended shapes) and
converted to meshes, then covered in soft particle fur shaded with the
Principled Hair BSDF. Markings are painted procedurally in object space, so the
same colour masks drive both the skin and the fur. Eyes and nose get their own
procedural textures (iris and pupil, bumpy nose leather).

Run headless, one mood per invocation:

    Blender --background --python tools/blender/dog.py -- --mood awake --out build/frames/awake
    Blender --background --python tools/blender/dog.py -- --dog nova --mood awake --still build/nova.png

Moods: awake (head tilt, blink, tail wag), happy (tongue out, bounce, fast wag),
sleepy (lying down, slow breathing, rising Zzz). Every animation is FRAMES long
and loops seamlessly.
"""

import argparse
import math
import sys
from pathlib import Path

import bmesh
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
# Nova, golden long-haired dachshund
GOLD = (0.36, 0.15, 0.045)
LIGHT_GOLD = (0.55, 0.32, 0.13)
CREAM = (0.78, 0.62, 0.40)
AMBER = (0.11, 0.045, 0.014)
SADDLE = (0.20, 0.08, 0.025)
# Ozzie, red cattle dog mix
RED = (0.42, 0.17, 0.06)
DARK_RED = (0.15, 0.06, 0.025)
EAR_DARK = (0.07, 0.03, 0.015)
STRAW = (0.42, 0.27, 0.11)
STRAW_DARK = (0.20, 0.12, 0.045)
COLLAR_RED = (0.55, 0.02, 0.03)
STONE = (0.10, 0.13, 0.17)
BALL = (0.50, 0.70, 0.05)
ZZZ = (0.04, 0.22, 1.0)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--dog", choices=["puppy", "nova", "ozzie"], default="puppy")
    p.add_argument("--mood", choices=["awake", "happy", "sleepy", "walk", "walkin"], default="awake")
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
    # velocity: out along the normal, combed back toward the tail and down.
    # Combing straight down would cancel the fur on upward-facing surfaces
    # (a bald back with a long, droopy coat).
    s.use_advanced_hair = True
    s.normal_factor = length
    s.object_align_factor = (0, 0.6 * droop * length, -0.6 * droop * length)
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

def build_puppy(pose):
    """Sculpt the tri-colour hound puppy. The head is modelled around a pivot at (0, -0.05, 0.95)
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
    if not lying:
        name_collar("MI11IE", (0, -0.03, 0.60), 0.17, 20, COLLAR_RED, root)

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
    millie_head(rig, head_pivot)

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


def build_nova(pose):
    """Nova: a golden long-haired dachshund. Sitting up on a long chest with
    short legs, a long narrow muzzle, and long silky feathered ears and tail.
    Lying, she stretches out long and low with her chin on her front paws."""
    if pose == "walking":
        sys.exit("nova: the walking pose isn't modelled yet")
    lying = pose == "lying"
    root = empty("root", (0, 0, 0))
    rig = {"root": root}
    if lying:
        body = [
            ((0, 0.18, 0.18), (0.21, 0.36, 0.15)),
            ((0, -0.10, 0.20), (0.18, 0.16, 0.14)),
            ((0, -0.16, 0.27), (0.13, 0.12, 0.12)),
        ]
        for side in (-1, 1):
            body += [
                ((side * 0.15, 0.36, 0.12), (0.11, 0.15, 0.10)),
                ((side * 0.09, -0.26, 0.045), (0.055, 0.12, 0.045)),
                ((side * 0.09, -0.36, 0.04), (0.06, 0.08, 0.04)),
                ((side * 0.20, 0.22, 0.04), (0.055, 0.09, 0.04)),
            ]
        body_patches = [
            (SADDLE, (0, 0.18, 0.33), (0.22, 0.40, 0.09)),
            (CREAM, (0, -0.20, 0.16), (0.13, 0.14, 0.10)),
        ]
    else:
        body = [
        ((0, 0.01, 0.43), (0.22, 0.21, 0.26), (-10, 0, 0)),
        ((0, 0.12, 0.18), (0.24, 0.26, 0.15)),
        ((0, -0.05, 0.66), (0.15, 0.14, 0.13)),
        ]
        for side in (-1, 1):
            body += [
                ((side * 0.16, 0.14, 0.14), (0.12, 0.16, 0.11)),
                ((side * 0.09, -0.15, 0.11), (0.055, 0.055, 0.09)),
                ((side * 0.09, -0.20, 0.035), (0.06, 0.08, 0.035)),
                ((side * 0.21, -0.04, 0.035), (0.055, 0.09, 0.035)),
            ]
        # Darker along the back, pale chest, so her shape reads on black
        body_patches = [
            (SADDLE, (0, 0.20, 0.50), (0.26, 0.13, 0.30)),
            (CREAM, (0, -0.18, 0.45), (0.12, 0.10, 0.28)),
            (CREAM, (0, -0.10, 0.66), (0.08, 0.07, 0.11)),
        ]
    # Silky coat that lies flat; the long feathering is on the ears and tail
    rig["torso"] = sculpt("body", body, coat_materials("body", GOLD, body_patches), root,
                          fur=(0.032, 7000, 0.8))

    if lying:
        # Lies along the ground, curving round her hip
        tail_root = empty("tail_root", (0.10, 0.52, 0.10), root)
        steps = [(0.0, 0.0, 0.0), (0.05, 0.03, -0.02), (0.11, 0.03, -0.04), (0.17, 0.0, -0.05),
                 (0.22, -0.05, -0.05)]
    else:
        tail_root = empty("tail_root", (0.10, 0.30, 0.08), root)
        steps = [(0.0, 0.0, 0.0), (0.05, 0.02, 0.0), (0.10, 0.04, 0.02), (0.15, 0.04, 0.04),
                 (0.20, 0.02, 0.07), (0.25, -0.01, 0.10)]
    rig["tail"] = tail_root
    base = Vector(tail_root.location)
    tail = [(tuple(base + Vector(d)), (0.045, 0.045, 0.05)) for d in steps]
    sculpt("tail", tail, coat_materials("tail", SADDLE), tail_root, fur=(0.08, 9000, 0.7))

    head_pivot = empty("head_pivot", (0, -0.05, 0.95), root)
    rig["head"] = head_pivot
    nova_head(rig, head_pivot)

    head_pivot.scale = (1.30,) * 3
    if lying:
        head_pivot.location = (0, -0.34, 0.17)
        head_pivot.rotation_euler = (math.radians(14), math.radians(-14), math.radians(12))
        root.rotation_euler = (0, 0, math.radians(-38))
        root.location = (0.14, 0.18, 0)
    else:
        head_pivot.location = (0, -0.07, 0.68)
        head_pivot.rotation_euler = (0, math.radians(6), math.radians(-18))
    # She's the smallest dog, which also leaves room under the clock for the hat
    root.scale = (0.88,) * 3
    return rig


def build_ozzie(pose):
    """Ozzie: a red Australian cattle dog mix. Lean and leggy, ginger with a
    darker saddle, white blaze, muzzle, chest and legs, one pricked ear and one
    folded, and a bushy banded tail with a white tip.

    The walking pose stands her up with four separate legs that swing from the
    shoulders and hips (fur hides the joins), carrying her ball in her mouth."""
    root = empty("root", (0, 0, 0))
    rig = {"root": root}
    if pose == "walking":
        head_pivot = ozzie_standing(rig)
    elif pose == "lying":
        head_pivot = ozzie_lying(rig)
    else:
        head_pivot = ozzie_sitting(rig)
    ozzie_head(rig, head_pivot, ball=pose == "walking")
    if pose == "walking":
        head_pivot.scale = (1.25,) * 3
        head_pivot.location = (0, -0.36, 0.66)
        # Faces her direction of travel, looking round towards the camera
        head_pivot.rotation_euler = (math.radians(10), 0, math.radians(-35))
        root.rotation_euler = (0, 0, math.radians(70))
        root.location = (-0.05, 0, 0)
    elif pose == "lying":
        # Chin on her front paws, like Millie
        head_pivot.scale = (1.32,) * 3
        head_pivot.location = (0, -0.31, 0.21)
        head_pivot.rotation_euler = (math.radians(14), math.radians(-14), math.radians(12))
        root.rotation_euler = (0, 0, math.radians(-38))
        root.location = (0.14, 0.18, 0)
    else:
        head_pivot.scale = (1.32,) * 3
        head_pivot.location = (0, -0.06, 0.70)
        head_pivot.rotation_euler = (0, math.radians(6), 0)
    return rig


def ozzie_sitting(rig):
    root = rig["root"]
    body = [
        ((0, 0.03, 0.45), (0.19, 0.18, 0.26), (-8, 0, 0)),
        ((0, 0.10, 0.21), (0.20, 0.21, 0.14)),
        ((0, -0.04, 0.68), (0.14, 0.13, 0.13)),
    ]
    for side in (-1, 1):
        body += [
            ((side * 0.14, 0.10, 0.17), (0.10, 0.16, 0.13)),
            ((side * 0.085, -0.12, 0.22), (0.05, 0.05, 0.20)),
            ((side * 0.085, -0.17, 0.04), (0.055, 0.08, 0.04)),
            ((side * 0.19, -0.05, 0.04), (0.055, 0.09, 0.04)),
        ]
    body_patches = [
        (DARK_RED, (0, 0.18, 0.55), (0.22, 0.14, 0.24)),
        (WHITE, (0, -0.16, 0.45), (0.10, 0.10, 0.27)),
        (WHITE, (0, -0.12, 0.68), (0.08, 0.07, 0.12)),
    ]
    for side in (-1, 1):
        body_patches += [
            (WHITE, (side * 0.085, -0.15, 0.13), (0.08, 0.09, 0.15)),
            (WHITE, (side * 0.19, -0.05, 0.04), (0.08, 0.12, 0.06)),
        ]
    rig["torso"] = sculpt("body", body, coat_materials("body", RED, body_patches), root,
                          fur=(0.03, 7000, 0.5))

    # Bushy tail curling up, with a dark band and a white tip
    tail_root = empty("tail_root", (0.12, 0.24, 0.10), root)
    rig["tail"] = tail_root
    base = Vector(tail_root.location)
    steps = [(0.0, 0.0, 0.0), (0.05, 0.02, 0.01), (0.10, 0.03, 0.04), (0.15, 0.02, 0.08),
             (0.19, 0.0, 0.13), (0.22, -0.03, 0.19), (0.23, -0.06, 0.24), (0.23, -0.08, 0.28)]
    tail = [(tuple(base + Vector(d)), (0.055, 0.055, 0.06)) for d in steps]
    tail_patches = [(EAR_DARK, tuple(base + Vector(steps[5])), (0.08, 0.08, 0.05)),
                    (WHITE, tuple(base + Vector(steps[7])), (0.07, 0.07, 0.06))]
    sculpt("tail", tail, coat_materials("tail", RED, tail_patches), tail_root, fur=(0.06, 9000, 0.3))
    return empty("head_pivot", (0, -0.05, 0.95), root)


def ozzie_lying(rig):
    root = rig["root"]
    body = [
        ((0, 0.20, 0.20), (0.20, 0.34, 0.16)),
        ((0, -0.06, 0.25), (0.17, 0.15, 0.16)),
        ((0, -0.12, 0.33), (0.13, 0.13, 0.13)),
    ]
    for side in (-1, 1):
        body += [
            ((side * 0.15, 0.38, 0.15), (0.11, 0.17, 0.12)),
            ((side * 0.09, -0.20, 0.06), (0.055, 0.19, 0.055)),
            ((side * 0.09, -0.42, 0.045), (0.06, 0.09, 0.045)),
            ((side * 0.21, 0.20, 0.045), (0.06, 0.10, 0.045)),
        ]
    body_patches = [
        (DARK_RED, (0, 0.20, 0.36), (0.22, 0.34, 0.10)),
        (WHITE, (0, -0.16, 0.20), (0.13, 0.15, 0.12)),
    ]
    for side in (-1, 1):
        body_patches += [
            (WHITE, (side * 0.09, -0.32, 0.06), (0.08, 0.18, 0.08)),
            (WHITE, (side * 0.21, 0.20, 0.045), (0.08, 0.12, 0.07)),
        ]
    rig["torso"] = sculpt("body", body, coat_materials("body", RED, body_patches), root,
                          fur=(0.03, 7000, 0.5))

    # Tail curled round on the ground beside her
    tail_root = empty("tail_root", (0.12, 0.52, 0.14), root)
    rig["tail"] = tail_root
    base = Vector(tail_root.location)
    steps = [(0.0, 0.0, 0.0), (0.06, 0.04, -0.03), (0.13, 0.03, -0.06), (0.19, -0.02, -0.08),
             (0.23, -0.09, -0.09), (0.24, -0.16, -0.09)]
    tail = [(tuple(base + Vector(d)), (0.055, 0.055, 0.055)) for d in steps]
    tail_patches = [(EAR_DARK, tuple(base + Vector(steps[4])), (0.07, 0.07, 0.06)),
                    (WHITE, tuple(base + Vector(steps[5])), (0.07, 0.07, 0.06))]
    sculpt("tail", tail, coat_materials("tail", RED, tail_patches), tail_root, fur=(0.06, 9000, 0.3))
    return empty("head_pivot", (0, -0.05, 0.95), root)


def ozzie_standing(rig):
    """Standing on all fours, facing -Y like every other pose; the root turns
    her side-on afterwards. Each leg hangs from a pivot at its top."""
    root = rig["root"]
    body = [
        ((0, -0.15, 0.43), (0.15, 0.17, 0.16)),
        ((0, 0.03, 0.43), (0.14, 0.18, 0.14)),
        ((0, 0.21, 0.44), (0.14, 0.15, 0.14)),
        ((0, -0.29, 0.56), (0.11, 0.12, 0.15), (-30, 0, 0)),
    ]
    body_patches = [
        (DARK_RED, (0, 0.05, 0.57), (0.18, 0.32, 0.08)),
        (WHITE, (0, -0.30, 0.44), (0.10, 0.10, 0.15)),
        (WHITE, (0, -0.02, 0.29), (0.12, 0.24, 0.06)),
    ]
    rig["torso"] = sculpt("body", body, coat_materials("body", RED, body_patches), root,
                          fur=(0.03, 7000, 0.5))

    rig["legs"] = {}
    for side in (-1, 1):
        x, y = side * 0.085, -0.17
        front = [((x, y, 0.32), (0.055, 0.06, 0.10)),
                 ((x, y - 0.01, 0.16), (0.04, 0.04, 0.11)),
                 ((x, y - 0.04, 0.03), (0.05, 0.07, 0.03))]
        rig["legs"][("front", side)] = leg(f"front_leg{side}", (x, y, 0.42), front, RED,
                                           [(WHITE, (x, y, 0.12), (0.08, 0.09, 0.17))], root)
        x, y = side * 0.09, 0.22
        hind = [((x, y, 0.32), (0.07, 0.10, 0.12)),
                ((x, y + 0.04, 0.15), (0.04, 0.045, 0.10), (-12, 0, 0)),
                ((x, y + 0.01, 0.03), (0.05, 0.07, 0.03))]
        rig["legs"][("hind", side)] = leg(f"hind_leg{side}", (x, y, 0.42), hind, RED,
                                          [(WHITE, (x, y + 0.02, 0.07), (0.08, 0.10, 0.12))], root)

    # Bushy tail held up and curling forward over the back
    tail_root = empty("tail_root", (0, 0.33, 0.48), root)
    rig["tail"] = tail_root
    base = Vector(tail_root.location)
    steps = [(0, 0.0, 0.0), (0, 0.05, 0.04), (0, 0.08, 0.10), (0, 0.08, 0.16),
             (0, 0.05, 0.21), (0, 0.0, 0.24), (0, -0.04, 0.24), (0, -0.07, 0.22)]
    tail = [(tuple(base + Vector(d)), (0.055, 0.055, 0.06)) for d in steps]
    tail_patches = [(EAR_DARK, tuple(base + Vector(steps[5])), (0.08, 0.08, 0.05)),
                    (WHITE, tuple(base + Vector(steps[7])), (0.07, 0.07, 0.06))]
    sculpt("tail", tail, coat_materials("tail", RED, tail_patches), tail_root, fur=(0.06, 9000, 0.3))
    return empty("head_pivot", (0, -0.05, 0.95), root)


def leg(name, top, elements, base, patches, parent):
    """A leg that swings from a pivot at its top (shoulder or hip)."""
    pivot = empty(f"{name}_pivot", top, parent)
    sculpt(name, elements, coat_materials(name, base, patches), pivot, fur=(0.022, 7000, 0.5))
    return pivot


def millie_head(rig, head_pivot):
    """Millie's head: tan with a black cap, white blaze and muzzle, long hound
    ears, and her captain's hat."""
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

    add_face(rig, head_mesh, head_pivot, nose_z=1.075, eye_x=0.10, eye_z=1.165, eye_r=0.055,
             tongue_loc=(0, -0.36, 0.95))
    # Long, soft hound ears with dark edges
    rig["ears"] = [drop_ear(side, (side * 0.19, -0.05, 1.27), TAN, head_pivot, fur=(0.022, 12000, 0.6),
                            tip=(DARK_TAN, (0.12, 0.08, 0.09))) for side in (-1, 1)]

    hat = captain_hat((0, -0.07, 1.34), (18, -10, 0), head_pivot)
    hat.scale = (0.93,) * 3


def nova_head(rig, head_pivot):
    """Nova's head: a long golden muzzle, long feathered ears, and her sombrero."""
    head = [
        ((0, -0.05, 1.18), (0.19, 0.20, 0.18)),
        ((0, -0.17, 1.21), (0.13, 0.09, 0.09)),
        ((-0.09, -0.16, 1.08), (0.09, 0.09, 0.08)),
        ((0.09, -0.16, 1.08), (0.09, 0.09, 0.08)),
        ((0, -0.26, 1.08), (0.095, 0.11, 0.075)),
        ((0, -0.37, 1.055), (0.07, 0.10, 0.06)),
        ((0, -0.30, 1.00), (0.06, 0.10, 0.04)),
    ]
    head_patches = [(LIGHT_GOLD, (0, -0.36, 1.03), (0.09, 0.14, 0.08))]
    head_mesh = sculpt("head", head, coat_materials("head", GOLD, head_patches), head_pivot,
                       fur=(0.018, 12000, 0.3))
    add_face(rig, head_mesh, head_pivot, nose_z=1.075, eye_x=0.085, eye_z=1.17, eye_r=0.05)
    # Long feathered ears reaching down past the jaw
    rig["ears"] = [drop_ear(side, (side * 0.12, -0.02, 1.25), AMBER, head_pivot, fur=(0.045, 12000, 1.0),
                            length=1.05, width=0.85) for side in (-1, 1)]

    sombrero((0, -0.05, 1.31), (14, 10, 0), head_pivot)


def ozzie_head(rig, head_pivot, ball):
    rig["head"] = head_pivot
    head = [
        ((0, -0.04, 1.18), (0.20, 0.19, 0.18)),
        ((0, -0.16, 1.21), (0.14, 0.09, 0.09)),
        ((-0.10, -0.14, 1.09), (0.10, 0.09, 0.09)),
        ((0.10, -0.14, 1.09), (0.10, 0.09, 0.09)),
        ((0, -0.24, 1.08), (0.10, 0.11, 0.08)),
        ((0, -0.35, 1.05), (0.07, 0.10, 0.06)),
        ((0, -0.28, 1.00), (0.06, 0.09, 0.04)),
    ]
    head_patches = [
        (DARK_RED, (0, 0.05, 1.36), (0.26, 0.26, 0.12)),
        (WHITE, (0, -0.22, 1.22), (0.035, 0.12, 0.17)),
        (WHITE, (0, -0.36, 1.03), (0.10, 0.14, 0.09)),
        (WHITE, (0, -0.22, 0.97), (0.08, 0.10, 0.06)),
    ]
    head_mesh = sculpt("head", head, coat_materials("head", RED, head_patches), head_pivot,
                       fur=(0.016, 12000, 0.3))
    add_face(rig, head_mesh, head_pivot, nose_z=1.07, eye_x=0.095, eye_z=1.17, eye_r=0.048)
    rig["ears"] = [prick_ear(1, (0.13, -0.02, 1.30), head_pivot),
                   folded_ear(-1, (-0.13, -0.02, 1.30), head_pivot)]
    if ball:
        # Held in her mouth, just under the nose; sized to match the ball on
        # the ground once the head is scaled up
        rig["ball_centre"] = Vector((0, -0.385, 0.975))
        rig["ball"] = tennis_ball(tuple(rig["ball_centre"]), 0.0644, head_pivot)


DOGS = {"puppy": build_puppy, "nova": build_nova, "ozzie": build_ozzie}


def require_sitting(name, pose):
    if pose != "sitting":
        sys.exit(f"{name}: only the sitting pose is modelled so far")


def add_face(rig, head_mesh, head_pivot, nose_z, eye_x, eye_z, eye_r, tongue_loc=None, nose_size=1.0):
    """Nose and eyes placed on the sculpted head by ray casting, plus the
    tongue (shown only when happy) just under the nose. nose_size scales the
    nose for a narrower muzzle, and sets it back into the muzzle to match."""
    k = nose_size
    nose_y = (surface_y(head_mesh, 0, nose_z) or -0.40) - 0.01 * k + 0.02 * (1 - k)
    nose = [((0, nose_y, nose_z), (0.06 * k, 0.04 * k, 0.04 * k)),
            ((-0.022 * k, nose_y - 0.008 * k, nose_z - 0.006 * k), (0.035 * k, 0.03 * k, 0.03 * k)),
            ((0.022 * k, nose_y - 0.008 * k, nose_z - 0.006 * k), (0.035 * k, 0.03 * k, 0.03 * k))]
    sculpt("nose", nose, [nose_material()], head_pivot, resolution=0.006)

    eye_mat = eye_material(eye_r)
    sparkle = emissive_material("sparkle", (1, 1, 1), 2.0)
    rig["eyes"] = []
    for side in (-1, 1):
        ex = side * eye_x
        ey = (surface_y(head_mesh, ex, eye_z) or -0.30) + eye_r * 0.15
        eye = blob(f"eye{side}", (ex, ey, eye_z), (eye_r, eye_r * 0.8, eye_r), eye_mat, head_pivot)
        blob(f"sparkle{side}", (ex - 0.016, ey - eye_r * 0.78, eye_z + 0.018), (0.008, 0.004, 0.008), sparkle, eye, segments=16)
        rig["eyes"].append(eye)

    tongue_loc = tongue_loc or (0, nose_y + 0.04, nose_z - 0.125)
    rig["tongue"] = blob("tongue", tongue_loc, (0.04, 0.025, 0.055), glossy_material("tongue", TONGUE, 0.3, 0.3), head_pivot)


def drop_ear(side, pivot_loc, color, head_pivot, fur, length=1.0, width=1.0, tip=None):
    """A soft hanging ear: a narrow top melting into a wide rounded flap.
    tip is an optional (colour, radii) patch at the bottom edge."""
    px, py, pz = pivot_loc
    pivot = empty(f"ear_pivot{side}", pivot_loc, head_pivot)
    x = px + side * 0.04 * width
    ear = [((x, py + 0.01, pz - 0.04 * length), (0.06 * width, 0.03, 0.07 * length)),
           ((x + side * 0.03 * width, py, pz - 0.18 * length), (0.10 * width, 0.03, 0.13 * length)),
           ((x + side * 0.05 * width, py - 0.01, pz - 0.30 * length), (0.09 * width, 0.03, 0.09 * length))]
    ear = [(c, s, (0, side * -10, 0)) for c, s in ear]
    patches = []
    if tip:
        patches = [(tip[0], (x + side * 0.05 * width, py - 0.01, pz - 0.36 * length), tip[1])]
    sculpt(f"ear{side}", ear, coat_materials(f"ear{side}", color, patches), pivot, fur=fur)
    return pivot


def prick_ear(side, pivot_loc, head_pivot):
    """An upright, pointed ear with a dark tip, leaning a little outward."""
    px, py, pz = pivot_loc
    pivot = empty(f"ear_pivot{side}", pivot_loc, head_pivot)
    ear = [((px, py, pz + 0.02), (0.075, 0.03, 0.06)),
           ((px + side * 0.02, py, pz + 0.09), (0.055, 0.025, 0.055)),
           ((px + side * 0.035, py, pz + 0.15), (0.03, 0.02, 0.04))]
    ear = [(c, s, (0, side * 15, 0)) for c, s in ear]
    patches = [(EAR_DARK, (px + side * 0.035, py, pz + 0.18), (0.05, 0.05, 0.05))]
    sculpt(f"ear{side}", ear, coat_materials(f"ear{side}", RED, patches), pivot, fur=(0.015, 12000, 0.2))
    return pivot


def folded_ear(side, pivot_loc, head_pivot):
    """An ear that stands up at the base and folds forward and down."""
    px, py, pz = pivot_loc
    pivot = empty(f"ear_pivot{side}", pivot_loc, head_pivot)
    ear = [((px, py, pz + 0.03), (0.075, 0.03, 0.06)),
           ((px + side * 0.05, py - 0.06, pz + 0.04), (0.065, 0.03, 0.06), (-40, 0, 0)),
           ((px + side * 0.08, py - 0.11, pz - 0.03), (0.05, 0.025, 0.05), (-70, 0, 0))]
    sculpt(f"ear{side}", ear, coat_materials(f"ear{side}", EAR_DARK), pivot, fur=(0.015, 12000, 0.4))
    return pivot


def lathe(name, profile, segments=64):
    """A surface of revolution around Z from (radius, height) pairs; a zero
    radius closes the surface to a point."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segments),
                                        r * math.sin(2 * math.pi * i / segments), z)) for i in range(segments)])
    for a, b in zip(rings, rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            if len(b) == 1:
                bm.faces.new((a[i], a[j], b[0]))
            elif len(a) == 1:
                bm.faces.new((a[0], b[j], b[i]))
            else:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def straw_material():
    """Coiled straw: concentric rings with a woven bump."""
    mat = bpy.data.materials.new("straw")
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.75
    coords = nodes.new("ShaderNodeTexCoord")
    rings = _node(nodes, "ShaderNodeTexWave", Scale=55.0, Distortion=1.5, Detail=3.0)
    rings.wave_type = "RINGS"
    links.new(coords.outputs["Object"], rings.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*STRAW_DARK, 1)
    ramp.color_ramp.elements[1].color = (*STRAW, 1)
    links.new(rings.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = _node(nodes, "ShaderNodeBump", Strength=0.4, Distance=0.003)
    links.new(rings.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def rainbow_material():
    """Shiny metallic foil whose hue runs around the hat's axis."""
    mat = glossy_material("rainbow", (1, 1, 1), 0.2, 0.3)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 1.0
    coords = nodes.new("ShaderNodeTexCoord")
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coords.outputs["Object"], xyz.inputs[0])
    angle = nodes.new("ShaderNodeMath")
    angle.operation = "ARCTAN2"
    links.new(xyz.outputs["Y"], angle.inputs[0])
    links.new(xyz.outputs["X"], angle.inputs[1])
    turns = nodes.new("ShaderNodeMath")
    turns.operation = "MULTIPLY"
    turns.inputs[1].default_value = 4 / (2 * math.pi)
    links.new(angle.outputs[0], turns.inputs[0])
    hue = nodes.new("ShaderNodeMath")
    hue.operation = "FRACT"
    links.new(turns.outputs[0], hue.inputs[0])
    hsv = nodes.new("ShaderNodeCombineColor")
    hsv.mode = "HSV"
    hsv.inputs[1].default_value = 0.85
    hsv.inputs[2].default_value = 0.9
    links.new(hue.outputs[0], hsv.inputs[0])
    links.new(hsv.outputs[0], bsdf.inputs["Base Color"])
    return mat


def sombrero(loc, rot, parent):
    """Nova's little straw sombrero: a tall pointed crown and an upturned brim,
    with a rainbow foil hat band and rim trim."""
    pivot = empty("hat", loc)
    pivot.rotation_euler = [math.radians(a) for a in rot]
    straw = straw_material()
    rainbow = rainbow_material()
    hat = lathe("sombrero", [(0.28, 0.045), (0.27, 0.022), (0.245, 0.007), (0.19, 0.0), (0.15, 0.0),
                             (0.12, 0.004), (0.118, 0.05), (0.108, 0.10), (0.088, 0.15),
                             (0.06, 0.19), (0.03, 0.212), (0.0, 0.218)])
    band = lathe("hat_band", [(0.125, 0.006), (0.122, 0.05)])
    rim = lathe("hat_rim", [(0.272, 0.034), (0.288, 0.046), (0.281, 0.058)])
    for obj, mat, thickness in ((hat, straw, 0.006), (band, rainbow, 0.006), (rim, rainbow, 0.004)):
        obj.data.materials.append(mat)
        solid = obj.modifiers.new("solid", "SOLIDIFY")
        solid.thickness = thickness
        solid.offset = 0
        obj.parent = pivot
    set_parent(pivot, parent)
    return pivot


def captain_hat(loc, rot, parent):
    """Millie's little captain's hat: a white crown wider than its navy band,
    a glossy black peak, a gold cord across the front and a gold badge."""
    pivot = empty("hat", loc)
    pivot.rotation_euler = [math.radians(a) for a in rot]
    white = glossy_material("hat_white", (0.82, 0.82, 0.80), 0.55, 0.0)
    navy = glossy_material("hat_band", (0.02, 0.03, 0.09), 0.5, 0.0)
    black = glossy_material("hat_peak", (0.01, 0.01, 0.012), 0.12, 1.0)
    gold = glossy_material("hat_gold", (0.8, 0.52, 0.12), 0.25, 0.6)
    crown = lathe("hat_crown", [(0.118, 0.045), (0.125, 0.07), (0.15, 0.10), (0.155, 0.115),
                                (0.14, 0.128), (0.08, 0.134), (0.0, 0.135)])
    band = lathe("hat_band", [(0.118, 0.0), (0.12, 0.024), (0.12, 0.047), (0.118, 0.05)])
    for obj, mat in ((crown, white), (band, navy)):
        obj.data.materials.append(mat)
        solid = obj.modifiers.new("solid", "SOLIDIFY")
        solid.thickness = 0.006
        solid.offset = 0
        obj.parent = pivot
    # The peak: a flattened disc sticking out at the front, tipped down
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=48, ring_count=16)
    peak = bpy.context.active_object
    peak.name = "hat_peak"
    peak.scale = (0.12, 0.10, 0.009)
    peak.location = (0, -0.12, 0.016)
    peak.rotation_euler = (math.radians(-12), 0, 0)
    bpy.ops.object.shade_smooth()
    peak.data.materials.append(black)
    peak.parent = pivot
    # The gold cord across the front of the band, and the badge above it
    bpy.ops.mesh.primitive_torus_add(major_radius=0.123, minor_radius=0.005, major_segments=96, minor_segments=8)
    cord = bpy.context.active_object
    cord.name = "hat_cord"
    cord.location = (0, 0, 0.03)
    bpy.ops.object.shade_smooth()
    cord.data.materials.append(gold)
    cord.parent = pivot
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=32, ring_count=16)
    badge = bpy.context.active_object
    badge.name = "hat_badge"
    badge.scale = (0.03, 0.008, 0.024)
    badge.location = (0, -0.136, 0.082)
    badge.rotation_euler = (math.radians(-20), 0, 0)
    bpy.ops.object.shade_smooth()
    badge.data.materials.append(gold)
    badge.parent = pivot
    set_parent(pivot, parent)
    return pivot


def name_collar(text, loc, radius, tilt, color, parent, band=0.035, letters=0.062):
    """A flat collar band with the dog's name in raised white letters across
    the front, or a round gold tag if there's no name. tilt (degrees) tips the
    front down onto the chest; band is the band's thickness and letters their
    height."""
    pivot = empty("collar", loc)
    pivot.rotation_euler = (math.radians(tilt), 0, 0)
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=band, major_segments=96, minor_segments=16)
    strap = bpy.context.active_object
    strap.name = "collar_band"
    strap.scale = (1, 1, 1.6)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    strap.data.materials.append(glossy_material("collar_band", color, 0.4, 0.3))
    strap.parent = pivot

    if not text:
        # A tag hanging at the front
        bpy.ops.mesh.primitive_cylinder_add(radius=band * 1.5, depth=band * 0.5, vertices=32)
        tag = bpy.context.active_object
        tag.name = "collar_tag"
        tag.location = (0, -(radius + band * 0.9), -band * 1.9)
        tag.rotation_euler = (math.radians(90), 0, 0)
        bpy.ops.object.shade_smooth()
        tag.data.materials.append(glossy_material("collar_tag", (0.8, 0.55, 0.15), 0.25, 0.5))
        tag.parent = pivot
        set_parent(pivot, parent)
        return pivot

    letter_mat = emissive_material("collar_letters", (1, 1, 1), 0.6)
    # Fredoka (same as the clock) has a flagged 1 that can't be mistaken for an l
    font = bpy.data.fonts.load(str(Path(__file__).resolve().parents[1] / "fonts/Fredoka.ttf"))
    size = letters
    step = size * 0.70 / (radius + band)
    for i, ch in enumerate(text):
        a = (i - (len(text) - 1) / 2) * step
        bpy.ops.object.text_add()
        letter = bpy.context.active_object
        letter.data.body = ch
        letter.data.font = font
        letter.data.size = size
        letter.data.extrude = 0.003
        letter.data.offset = 0.0025  # bolder strokes so it reads at watch size
        letter.data.align_x = "CENTER"
        letter.data.align_y = "CENTER"
        letter.data.materials.append(letter_mat)
        r = radius + band + 0.001
        letter.location = (r * math.sin(a), -r * math.cos(a), 0)
        letter.rotation_euler = (math.radians(90), 0, a)
        letter.parent = pivot
    set_parent(pivot, parent)
    return pivot


def build_ground(ball):
    """The stones are the fixed set that every dog and animation shares; the
    ball is Ozzie's and only appears with her."""
    stone_mat = glossy_material("stone", STONE, 0.7, 0.0)
    for i, (x, y, s) in enumerate([(-0.36, -0.26, 0.09), (-0.22, -0.38, 0.065), (0.40, -0.20, 0.06)]):
        blob(f"stone{i}", (x, y, s * 0.3), (s * 1.3, s, s * 0.6), stone_mat, segments=24)
    if ball:
        tennis_ball((0.33, -0.40, 0.085), 0.085)


def tennis_ball(centre, radius, parent=None):
    skin, fur = coat_materials("ball", BALL)
    ball = sculpt("ball", [(centre, (radius,) * 3)], (skin, fur), parent, resolution=0.01)
    if not ARGS.no_fur:
        add_fur(ball, fur, radius * 0.094, 40000, 0.0)
    return ball


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


def pulse(frame, centre, width):
    """A quick bump peaking at `centre`, for one-off twitches in a loop."""
    return math.exp(-((frame - centre) / width) ** 2)


def animate(rig, mood, zzz):
    torso = rig["torso"]
    base_scale = tuple(torso.scale)
    head_rest = tuple(rig["head"].rotation_euler)
    head_loc = tuple(rig["head"].location)
    for f in range(1, FRAMES + 1):
        if mood == "sleepy":
            # One slow, deep breath per loop: the back rises and the head
            # lifts with it
            breath = 0.035 * wave(f, 1)
            key(torso, "scale", f, (base_scale[0] * (1 + breath * 0.6), base_scale[1] * (1 + breath * 0.3),
                                    base_scale[2] * (1 + breath)))
            key(rig["head"], "location", f, (head_loc[0], head_loc[1], head_loc[2] + 0.4 * breath))
        else:
            breath = 0.010 * wave(f, 2)
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
            # Dreaming: the head nods with each breath and the tail thumps once
            tilt = math.radians(3) * wave(f, 1, 0.1)
            wag = math.radians(8) * wave(f, 1) + math.radians(22) * (pulse(f, 19, 1.4) - 0.6 * pulse(f, 22, 1.4))
            blink = 0.06

        key(rig["head"], "rotation_euler", f, (head_rest[0], head_rest[1] + tilt, head_rest[2]))
        key(rig["tail"], "rotation_euler", f, (0, 0, wag))
        for eye in rig["eyes"]:
            key(eye, "scale", f, (1, 1, blink))
        for i, ear in enumerate(rig["ears"]):
            # Ears lag the head a little and flop the other way
            flop = -0.6 * tilt
            if mood == "sleepy":
                # A dreamy twitch of one ear, then the other a little later
                flop += math.radians(18) * pulse(f, 8 if i == 1 else 12, 1.2)
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


# Walk: legs move in the order left hind, left front, right hind, right front
WALK_PHASES = {("hind", -1): 0.0, ("front", -1): 0.25, ("hind", 1): 0.5, ("front", 1): 0.75}
STRIDES = 3


def animate_walk(rig):
    """A walk cycle in place: STRIDES strides per loop. Each leg swings about
    its top and shortens a little while it swings forward so the paw clears
    the ground; the body bobs twice per stride."""
    head_rest = tuple(rig["head"].rotation_euler)
    root_rest = tuple(rig["root"].location)
    for f in range(1, FRAMES + 1):
        for key_, pivot in rig["legs"].items():
            phi = 2 * math.pi * (STRIDES * (f - 1) / FRAMES + WALK_PHASES[key_])
            swing = math.radians(24) * math.sin(phi)
            # Forward swing is while the angle is falling (cos < 0)
            lift = max(0.0, -math.cos(phi))
            key(pivot, "rotation_euler", f, (swing, 0, 0))
            key(pivot, "scale", f, (1, 1, 1 - 0.14 * lift))
        bob = 0.012 * wave(f, 2 * STRIDES)
        key(rig["root"], "location", f, (root_rest[0], root_rest[1], root_rest[2] + bob))
        nod = math.radians(3) * wave(f, 2 * STRIDES, 0.15)
        key(rig["head"], "rotation_euler", f, (head_rest[0] + nod, head_rest[1], head_rest[2]))
        key(rig["tail"], "rotation_euler", f, (0, 0, math.radians(18) * wave(f, STRIDES)))
        for i, ear in enumerate(rig["ears"]):
            key(ear, "rotation_euler", f, (0, math.radians(4) * wave(f, 2 * STRIDES, 0.3 + i * 0.1), 0))
    rig["tongue"].hide_render = True


# Walk-in timeline (frames): walk at full speed, slow to a stop while turning
# to face the camera, then dip the head and drop the ball, which bounces and
# rolls to its spot in the sitting scene. The sit itself is a dissolve to the
# sitting render, done when the frames are assembled.
WALK_IN_FRAMES = 46
WALK_SPEED = 0.036          # world units per frame, matched to the stride
WALK_START_X = -1.06        # just out of the watch's crop
SLOW_FROM, STOP_AT = 26, 34
TURN_FROM, TURN_TO = 26, 36
DROP_AT = 38
BALL_REST = Vector((0.33, -0.40, 0.085))


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def animate_walk_in(rig):
    scene = bpy.context.scene
    scene.frame_end = WALK_IN_FRAMES
    root, head = rig["root"], rig["head"]
    head_rest = tuple(head.rotation_euler)
    x, phase = WALK_START_X, 0.0
    for f in range(1, WALK_IN_FRAMES + 1):
        if f <= SLOW_FROM:
            speed = 1.0
        else:
            speed = max(0.0, 1 - (f - SLOW_FROM) / (STOP_AT - SLOW_FROM))
        x += WALK_SPEED * speed
        phase += speed * STRIDES / FRAMES
        turn = smoothstep(TURN_FROM, TURN_TO, f)

        for key_, pivot in rig["legs"].items():
            phi = 2 * math.pi * (phase + WALK_PHASES[key_])
            key(pivot, "rotation_euler", f, (math.radians(24) * speed * math.sin(phi), 0, 0))
            key(pivot, "scale", f, (1, 1, 1 - 0.14 * speed * max(0.0, -math.cos(phi))))
        bob = 0.012 * speed * math.sin(4 * math.pi * phase)
        key(root, "location", f, (x, 0, bob))
        key(root, "rotation_euler", f, (0, 0, math.radians(70 - 70 * turn)))

        # Head: looks round at the camera while walking, straightens as the
        # body turns, then dips to drop the ball
        dip = math.radians(38) * max(0.0, 1 - abs(f - DROP_AT) / 4) ** 0.7
        nod = math.radians(3) * speed * math.sin(4 * math.pi * phase + 1)
        key(head, "rotation_euler", f, (head_rest[0] + nod + dip, head_rest[1],
                                        head_rest[2] + math.radians(35) * turn))
        key(rig["tail"], "rotation_euler", f, (0, 0, math.radians(18) * math.sin(2 * math.pi * phase)
                                                + math.radians(25) * (1 - speed) * wave(f, 4)))
        for i, ear in enumerate(rig["ears"]):
            key(ear, "rotation_euler", f, (0, math.radians(4) * speed * math.sin(4 * math.pi * phase + i), 0))

    # Swap the ball in her mouth for a loose one at the moment she lets go
    held = rig["ball"]
    scene.frame_set(DROP_AT)
    start = held.matrix_world @ rig["ball_centre"]
    loose = tennis_ball((0, 0, 0), 0.085)
    for f in range(1, WALK_IN_FRAMES + 1):
        held.hide_render = f >= DROP_AT
        held.keyframe_insert("hide_render", frame=f)
        loose.hide_render = f < DROP_AT
        loose.keyframe_insert("hide_render", frame=f)
        if f < DROP_AT:
            pos, spin = start, 0.0
        elif f <= DROP_AT + 3:
            # Falls straight down
            t = (f - DROP_AT) / 3
            pos = Vector((start.x, start.y, start.z + (BALL_REST.z - start.z) * t * t))
            spin = 0.0
        else:
            # Little bounce while it rolls to its resting place
            t = smoothstep(DROP_AT + 3, WALK_IN_FRAMES - 2, f)
            ground = start.lerp(BALL_REST, t)
            hop = 0.06 * max(0.0, math.sin(math.pi * (f - DROP_AT - 3) / 4)) if f < DROP_AT + 7 else 0.0
            pos = Vector((ground.x, ground.y, BALL_REST.z + hop))
            spin = (ground.xy - start.xy).length / 0.085
        key(loose, "location", f, tuple(pos))
        roll_axis = (BALL_REST.xy - start.xy).normalized()
        key(loose, "rotation_euler", f, (-roll_axis.y * spin, roll_axis.x * spin, 0))
    rig["tongue"].hide_render = True


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Every frame is keyed, so linear keys reproduce the curves exactly
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    setup_scene(ARGS.size, ARGS.samples)
    pose = {"sleepy": "lying", "walk": "walking", "walkin": "walking"}.get(ARGS.mood, "sitting")
    rig = DOGS[ARGS.dog](pose)
    build_ground(ball=ARGS.dog == "ozzie" and pose != "walking")
    zzz = build_zzz()
    if ARGS.mood == "walk":
        animate_walk(rig)
    elif ARGS.mood == "walkin":
        animate_walk_in(rig)
    else:
        animate(rig, ARGS.mood, zzz)
    for z in zzz:
        z.hide_render = ARGS.mood != "sleepy"
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


# Imported by the rig scripts (ozzie_rig.py), which set ARGS themselves
if __name__ == "__main__":
    ARGS = parse_args()
    main()
