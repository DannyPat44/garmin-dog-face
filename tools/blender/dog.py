"""Build and render the plush puppy in Blender.

Modelled on the tri-colour hound puppy in the reference photo: black saddle,
tan face and legs, white blaze, chest and paws, tan eyebrow dots, floppy ears.

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
from mathutils import Vector

FRAMES = 30
FPS = 10

# Coat colours, linear RGB
BLACK = (0.012, 0.010, 0.011)
TAN = (0.30, 0.125, 0.045)
WHITE = (0.86, 0.80, 0.71)
DARK_TAN = (0.10, 0.035, 0.012)
NOSE = (0.01, 0.01, 0.012)
EYE = (0.10, 0.038, 0.012)
TONGUE = (0.85, 0.22, 0.28)
BLUSH = (0.75, 0.22, 0.20)
FRECKLE = (0.30, 0.12, 0.05)
STONE = (0.03, 0.09, 0.20)
BALL = (0.55, 0.75, 0.05)
ZZZ = (0.04, 0.22, 1.0)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--mood", choices=["awake", "happy", "sleepy"], default="awake")
    p.add_argument("--out", help="directory for the PNG frame sequence")
    p.add_argument("--still", help="render only frame 1 to this PNG")
    p.add_argument("--size", type=int, default=480)
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--fur", action="store_true", help="add plush particle fur (slow)")
    p.add_argument("--blend", help="also save the .blend file here")
    return p.parse_args(argv)


# --- materials -------------------------------------------------------------

def _node(nodes, kind, **inputs):
    n = nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def coat_material(name, base, patches=(), roughness=0.78, sheen=0.0):
    """Fur-coloured material. Each patch is (colour, centre, radii): an
    ellipsoid in the object's local space, with a noisy edge, painted over the
    base colour in order. Object coordinates keep markings attached to the part
    as it animates, and hair strands pick up the colour at their root."""
    mat = bpy.data.materials.new(name)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = _node(nodes, "ShaderNodeBsdfPrincipled", Roughness=roughness)
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Roughness"].default_value = 0.4
    # Soft matte clay with a hint of subsurface warmth
    bsdf.inputs["Specular IOR Level"].default_value = 0.25
    bsdf.inputs["Subsurface Weight"].default_value = 0.04
    bsdf.inputs["Subsurface Radius"].default_value = (0.008, 0.005, 0.003)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    coords = nodes.new("ShaderNodeTexCoord")
    noise = _node(nodes, "ShaderNodeTexNoise", Scale=18.0, Detail=4.0)
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
        # Roughen the edge so patches read as fur markings, not decals
        wobble = nodes.new("ShaderNodeMath")
        wobble.operation = "MULTIPLY_ADD"
        wobble.inputs[1].default_value = 0.12
        links.new(noise.outputs["Fac"], wobble.inputs[0])
        links.new(length.outputs["Value"], wobble.inputs[2])
        mask = nodes.new("ShaderNodeMapRange")
        mask.interpolation_type = "SMOOTHSTEP"
        mask.inputs["From Min"].default_value = 1.15
        mask.inputs["From Max"].default_value = 1.0
        links.new(wobble.outputs[0], mask.inputs["Value"])
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["B"].default_value = (*patch_color, 1)
        links.new(mask.outputs["Result"], mix.inputs["Factor"])
        links.new(current, mix.inputs["A"])
        current = mix.outputs["Result"]
    links.new(current, bsdf.inputs["Base Color"])
    return mat


def glossy_material(name, color, roughness=0.15, coat=1.0):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Coat Weight"].default_value = coat
    return mat


def emissive_material(name, color, strength=0.8):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Emission Color"].default_value = (*color, 1)
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


# --- geometry --------------------------------------------------------------

def blob(name, loc, scale, mat, parent=None, rot=(0, 0, 0), fur=None, segments=48):
    """A smooth ellipsoid with its scale applied, so local coordinates (used by
    the coat patches and hair length) are in real units."""
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
    if fur and ARGS.fur:
        add_fur(obj, mat, *fur)
    return obj


def empty(name, loc, parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.location = loc
    bpy.context.collection.objects.link(obj)
    if parent:
        set_parent(obj, parent)
    return obj


def set_parent(child, parent):
    bpy.context.view_layer.update()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def add_fur(obj, mat, length, density):
    """Short plush fur from a hair particle system. density is parent strands
    per square metre of surface; children fill in at render time."""
    area = sum(p.area for p in obj.data.polygons)
    mod = obj.modifiers.new("fur", "PARTICLE_SYSTEM")
    s = mod.particle_system.settings
    s.type = "HAIR"
    s.count = max(200, int(area * density))
    s.hair_length = length
    s.hair_step = 4
    s.render_step = 3
    s.display_step = 2
    s.child_type = "INTERPOLATED"
    s.child_percent = 2
    s.rendered_child_count = 30
    s.child_length = 1.0
    s.child_length_threshold = 0.4
    s.clump_factor = 0.05
    s.roughness_1 = length * 0.5
    s.roughness_2 = length * 0.4
    s.roughness_endpoint = length * 0.4
    s.root_radius = 1.0
    s.tip_radius = 0.1
    s.radius_scale = 0.0012
    s.material_slot = mat.name


def build_dog(pose):
    """Build the puppy with chibi proportions: an oversized round head, big low
    eyes, a short muzzle and a small chubby body. Parts are laid out for the
    sitting pose; the sleepy pose lies the body down and rests the head on the
    front paws."""
    lying = pose == "lying"
    root = empty("root", (0, 0, 0))
    rig = {"root": root}

    body_fur = (0.034, 9000)
    head_fur = (0.026, 12000)
    leg_fur = (0.018, 12000)
    short_fur = (0.010, 16000)

    torso_mat = coat_material("torso", BLACK, [
        (TAN, (0, -0.10, -0.20), (0.32, 0.20, 0.18)),
        (WHITE, (0, -0.24, 0.0), (0.16, 0.14, 0.34)),
    ])
    if lying:
        rig["torso"] = blob("torso", (0, 0.20, 0.22), (0.27, 0.38, 0.22), torso_mat, root, fur=body_fur)
    else:
        rig["torso"] = blob("torso", (0, 0.06, 0.42), (0.23, 0.23, 0.32), torso_mat, root, rot=(-4, 0, 0), fur=body_fur)

    neck_mat = coat_material("neck", BLACK, [(WHITE, (0, -0.15, -0.02), (0.11, 0.09, 0.18))])
    neck_loc = (0, -0.14, 0.36) if lying else (0, -0.04, 0.64)
    blob("neck", neck_loc, (0.18, 0.17, 0.13), neck_mat, root, fur=body_fur)

    paw_mat = coat_material("paw", WHITE)
    haunch_mat = coat_material("haunch", BLACK, [(TAN, (0, -0.14, -0.05), (0.2, 0.13, 0.13))])
    for side in (-1, 1):
        if lying:
            leg_mat = coat_material("leg_lying", TAN, [(WHITE, (0, -0.18, 0), (0.3, 0.13, 0.3))])
            blob(f"leg{side}", (side * 0.12, -0.24, 0.08), (0.075, 0.18, 0.075), leg_mat, root, fur=leg_fur)
            blob(f"paw{side}", (side * 0.12, -0.44, 0.06), (0.09, 0.11, 0.065), paw_mat, root, fur=leg_fur)
            blob(f"haunch{side}", (side * 0.19, 0.34, 0.16), (0.15, 0.19, 0.15), haunch_mat, root, fur=body_fur)
            blob(f"backpaw{side}", (side * 0.25, 0.16, 0.05), (0.08, 0.11, 0.06), paw_mat, root, fur=leg_fur)
        else:
            leg_mat = coat_material("leg", TAN, [(WHITE, (0, 0, -0.17), (0.3, 0.3, 0.13))])
            blob(f"leg{side}", (side * 0.105, -0.15, 0.21), (0.07, 0.07, 0.19), leg_mat, root, fur=leg_fur)
            blob(f"paw{side}", (side * 0.105, -0.22, 0.06), (0.095, 0.12, 0.07), paw_mat, root, fur=leg_fur)
            blob(f"haunch{side}", (side * 0.17, 0.09, 0.16), (0.13, 0.18, 0.14), haunch_mat, root, fur=body_fur)
            blob(f"backpaw{side}", (side * 0.23, -0.08, 0.05), (0.085, 0.11, 0.06), paw_mat, root, fur=leg_fur)

    # Tail: a chain of segments curling out to the dog's left so it shows
    tail_root = empty("tail_root", (0.12, 0.50, 0.15) if lying else (0.13, 0.20, 0.09), root)
    rig["tail"] = tail_root
    tail_mat = coat_material("tail", BLACK)
    tail_tip_mat = coat_material("tail_tip", WHITE)
    base = Vector(tail_root.location)
    for i, (dx, dy, dz) in enumerate([(0.07, 0.05, 0.02), (0.17, 0.04, 0.06), (0.25, -0.02, 0.13), (0.30, -0.08, 0.21)]):
        mat = tail_tip_mat if i == 3 else tail_mat
        blob(f"tail{i}", base + Vector((dx, dy, dz)), (0.05, 0.05, 0.065), mat, tail_root, fur=leg_fur)

    # Head, modelled around a pivot at (0, -0.05, 0.95) and then scaled up
    # and moved onto the shorter neck
    head_pivot = empty("head_pivot", (0, -0.05, 0.95), root)
    rig["head"] = head_pivot
    head_scale = 1.45
    head_mat = coat_material("head", TAN, [
        (BLACK, (0, 0.10, 0.20), (0.33, 0.30, 0.17)),
        (BLACK, (0, 0.22, 0.0), (0.31, 0.15, 0.30)),
        (BLACK, (0, -0.19, 0.13), (0.22, 0.12, 0.07)),
        (TAN, (-0.09, -0.22, 0.135), (0.04, 0.06, 0.026)),
        (TAN, (0.09, -0.22, 0.135), (0.04, 0.06, 0.026)),
        (WHITE, (0, -0.25, 0.04), (0.045, 0.08, 0.22)),
        (BLUSH, (-0.18, -0.19, -0.07), (0.06, 0.06, 0.04)),
        (BLUSH, (0.18, -0.19, -0.07), (0.06, 0.06, 0.04)),
    ])
    blob("head", (0, -0.10, 1.15), (0.31, 0.27, 0.28), head_mat, head_pivot, fur=head_fur)
    freckles = [(FRECKLE, (x, -0.11, z), (0.011, 0.03, 0.011))
                for x, z in [(-0.07, 0.02), (-0.10, -0.01), (-0.05, -0.02), (0.07, 0.02), (0.10, -0.01), (0.05, -0.02), (-0.12, 0.03), (0.12, 0.03)]]
    muzzle_mat = coat_material("muzzle", WHITE, freckles)
    blob("muzzle", (0, -0.29, 1.03), (0.16, 0.11, 0.10), muzzle_mat, head_pivot, fur=short_fur)
    for side in (-1, 1):
        blob(f"jowl{side}", (side * 0.07, -0.31, 0.98), (0.075, 0.07, 0.065), paw_mat, head_pivot, fur=short_fur)
    blob("nose", (0, -0.405, 1.075), (0.075, 0.052, 0.052), glossy_material("nose", NOSE, 0.2, 0.8), head_pivot, rot=(10, 0, 0))
    mouth(head_pivot)

    # Big, low-set eyes with two catchlights each: the main source of cuteness
    eye_mat = glossy_material("eye", EYE, 0.05)
    rim_mat = glossy_material("eye_rim", NOSE, 0.3, 0.3)
    pupil_mat = glossy_material("pupil", NOSE, 0.05)
    sparkle = emissive_material("sparkle", (1, 1, 1), 3.0)
    rig["eyes"] = []
    for side in (-1, 1):
        ex, ez = side * 0.14, 1.15
        eye = blob(f"eye{side}", (ex, -0.335, ez), (0.068, 0.042, 0.072), eye_mat, head_pivot)
        blob(f"eye_rim{side}", (ex, -0.318, ez), (0.078, 0.04, 0.082), rim_mat, eye)
        blob(f"pupil{side}", (ex, -0.362, ez - 0.004), (0.042, 0.02, 0.045), pupil_mat, eye, segments=24)
        blob(f"sparkle{side}a", (ex - 0.022, -0.378, ez + 0.028), (0.018, 0.008, 0.018), sparkle, eye, segments=16)
        blob(f"sparkle{side}b", (ex + 0.024, -0.376, ez - 0.03), (0.008, 0.005, 0.008), sparkle, eye, segments=16)
        rig["eyes"].append(eye)

    ear_mat = coat_material("ear", TAN, [(DARK_TAN, (0, 0, -0.33), (0.16, 0.10, 0.12))])
    rig["ears"] = []
    for side in (-1, 1):
        pivot = empty(f"ear_pivot{side}", (side * 0.27, -0.05, 1.24), head_pivot)
        blob(f"ear{side}", (side * 0.35, -0.07, 0.97), (0.13, 0.05, 0.31), ear_mat, pivot,
             rot=(-6, side * -9, 0), fur=leg_fur)
        rig["ears"].append(pivot)

    tongue = blob("tongue", (0, -0.39, 0.96), (0.042, 0.025, 0.06), glossy_material("tongue", TONGUE, 0.3, 0.3), head_pivot)
    rig["tongue"] = tongue

    head_pivot.scale = (head_scale,) * 3
    if lying:
        # Rest the head on the front paws, chin down, and turn the dog
        # side-on so the body shows behind the head
        head_pivot.location = (0, -0.30, 0.25)
        head_pivot.rotation_euler = (math.radians(14), math.radians(-14), math.radians(12))
        root.rotation_euler = (0, 0, math.radians(-38))
        root.location = (0.14, 0.18, 0)
    else:
        # A slight resting head tilt
        head_pivot.location = (0, -0.06, 0.69)
        head_pivot.rotation_euler = (0, math.radians(7), 0)
    return rig


def mouth(parent):
    """A small 'w' smile under the nose."""
    curve = bpy.data.curves.new("mouth", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.005
    curve.bevel_resolution = 3
    spline = curve.splines.new("NURBS")
    pts = [(-0.07, 1.005), (-0.035, 0.985), (0.0, 1.008), (0.035, 0.985), (0.07, 1.005)]
    spline.points.add(len(pts) - 1)
    for p, (x, z) in zip(spline.points, pts):
        y = -0.402 + 0.5 * x * x
        p.co = (x, y, z, 1)
    spline.order_u = 3
    spline.use_endpoint_u = True
    curve.materials.append(glossy_material("mouth", NOSE, 0.4, 0.0))
    obj = bpy.data.objects.new("mouth", curve)
    bpy.context.collection.objects.link(obj)
    set_parent(obj, parent)
    return obj


def build_ground():
    stone_mat = glossy_material("stone", STONE, 0.6, 0.0)
    for i, (x, y, s) in enumerate([(-0.36, -0.26, 0.09), (-0.22, -0.38, 0.065), (0.40, -0.20, 0.06)]):
        blob(f"stone{i}", (x, y, s * 0.3), (s * 1.3, s, s * 0.6), stone_mat, segments=24)
    ball_mat = coat_material("ball", BALL, roughness=0.9, sheen=1.0)
    blob("ball", (0.33, -0.40, 0.085), (0.085, 0.085, 0.085), ball_mat, fur=(0.006, 30000), segments=32)


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
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.06, 1)

    cam_data = bpy.data.cameras.new("camera")
    cam_data.lens = 70
    cam = bpy.data.objects.new("camera", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.4, -3.8, 1.3)
    target = Vector((0.0, -0.10, 0.74))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    def area_light(name, loc, energy, size, color=(1, 1, 1)):
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.size, data.color = energy, size, color
        light = bpy.data.objects.new(name, data)
        light.location = loc
        light.rotation_euler = (Vector((0, 0, 0.7)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(light)

    # Big soft warm key, gentle fill, and strong rims to make the fur edges glow
    area_light("key", (-2.0, -3.2, 3.0), 1000, 4.0, (1.0, 0.92, 0.82))
    area_light("fill", (3.0, -2.5, 1.2), 300, 4.0, (0.88, 0.92, 1.0))
    area_light("rim", (1.8, 2.8, 1.2), 350, 2.5, (1.0, 0.95, 0.9))
    area_light("rim2", (-1.8, 2.6, 1.0), 200, 2.5, (0.9, 0.93, 1.0))


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
        breath = 0.012 * wave(f, 1 if mood == "sleepy" else 2)
        key(torso, "scale", f, (base_scale[0] * (1 + breath), base_scale[1] * (1 + breath), base_scale[2] * (1 + breath * 0.5)))

        if mood == "awake":
            tilt = math.radians(14) * max(0.0, wave(f, 1, 0.0)) ** 1.5
            wag = math.radians(28) * wave(f, 3)
            blink = 0.1 if f in (19, 20) else 1.0
        elif mood == "happy":
            tilt = math.radians(5) * wave(f, 2)
            wag = math.radians(40) * wave(f, 5)
            blink = 0.55
            key(rig["root"], "location", f, (0, 0, 0.025 * abs(wave(f, 2))))
        else:
            tilt = 0.0
            wag = math.radians(6) * wave(f, 1)
            blink = 0.08

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
