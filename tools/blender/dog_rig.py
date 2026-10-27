"""One skeleton for every dog: each dog is a spec (its torso, coat, head and
a few proportions) skinned onto the same rig, so they all stand, walk, sit
and lie down the same way.

Each dog's body and legs are one sculpt bound to the armature with automatic
weights, so poses and transitions are real bends at the joints (the fur rides
along). Poses are bone angles shared by every dog (a spec can adjust them);
the walk cycle and idle motions are offsets on top; the walk-in and walk-out
are timelines blending poses with easing. A carried ball is simulated when
dropped: gravity, bounces that lose height and speed, then rolling to a stop.

    Blender --background --python tools/blender/dog_rig.py -- --dog ozzie --anim walkin --out build/frames/rig/ozzie/walkin
    anims: walkin, walkout, awake, happy, sleepy, liedown, poses (key poses, one per frame)
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
import dog  # noqa: E402  (shared materials, heads, ground, scene)

FPS = 10
LOOP = 30


# --- dogs -------------------------------------------------------------------
#
# Coordinates are for the dog standing at the origin facing -Y (the camera
# looks from -Y). A spec gives:
#   torso      metaball ellipsoids for the body: (centre, semi-axes[, rotation])
#   front, hind  leg attachment: (x, y) and the height of the leg's top
#   leg        thickness scale for the legs
#   coat       base colour and patches (colour, centre, radii), painted in order;
#              "socks" colours the lower legs
#   tail       points along the tail and its radius
#   shoulder, hip  where the spine pivots (shoulders) and ends (hips)
#   neck       neck bone (base, top)
#   head       the head builder from dog.py, plus where the head pivot sits
#   fur        body fur (length, density, droop) and tail fur
#   fur_style  how the coat looks: one of FUR_STYLES
#   collar     (name, or "" for a gold tag, radius, tilt, colour[, band
#              thickness[, letter height]]), round the base of the neck or
#              at collar_at
#   poses      adjustments to the shared poses, by pose name

# A warm near-black for black coats: the fur's sheen keeps it visible on the
# watch's black
SADDLE_BLACK = (0.04, 0.032, 0.027)

SPECS = {
    "ozzie": {
        "torso": [
            ((0, -0.15, 0.43), (0.15, 0.17, 0.16)),
            ((0, 0.03, 0.43), (0.14, 0.18, 0.14)),
            ((0, 0.21, 0.44), (0.14, 0.15, 0.14)),
            ((0, -0.29, 0.56), (0.11, 0.12, 0.15), (-30, 0, 0)),
        ],
        "front": (0.085, -0.17, 0.42),
        "hind": (0.09, 0.22, 0.42),
        "leg": 1.0,
        "coat": (dog.RED, [
            (dog.DARK_RED, (0, 0.05, 0.57), (0.18, 0.32, 0.08)),
            # White bib up the front of the chest to the throat, as in her sitting render
            (dog.WHITE, (0, -0.33, 0.50), (0.11, 0.12, 0.21)),
            (dog.WHITE, (0, -0.02, 0.29), (0.12, 0.24, 0.06)),
        ]),
        "socks": dog.WHITE,
        "tail": ([(0, 0.31, 0.47), (0, 0.36, 0.55), (0, 0.37, 0.64), (0, 0.33, 0.71), (0, 0.27, 0.72)], 0.055,
                 [(dog.EAR_DARK, 3, (0.07, 0.07, 0.05)), (dog.WHITE, 4, (0.07, 0.07, 0.06))]),
        "shoulder": (0, -0.15, 0.45),
        "hip": (0, 0.24, 0.44),
        "neck": ((0, -0.28, 0.58), (0, -0.34, 0.68)),
        "head": ("ozzie", (0, -0.36, 0.62), 1.32),
        "scale": 0.9,
        "fur": ((0.03, 7000, 0.5), (0.06, 9000, 0.3)),
        "fur_style": "coarse",
        "ball": True,
        # Sitting, her head tilts a little, inquisitively
        "poses": {"sit": {"neck": (-6, 6, 0)}},
    },
    # A long, low golden dachshund: short legs, long body, silky coat
    "nova": {
        "torso": [
            ((0, -0.22, 0.30), (0.16, 0.17, 0.15)),
            ((0, 0.04, 0.29), (0.165, 0.22, 0.145)),
            ((0, 0.28, 0.31), (0.155, 0.16, 0.14)),
            ((0, -0.35, 0.41), (0.115, 0.12, 0.13), (-30, 0, 0)),
        ],
        "front": (0.09, -0.25, 0.24),
        "hind": (0.10, 0.31, 0.24),
        "leg": 1.1,
        "coat": (dog.GOLD, [
            (dog.SADDLE, (0, 0.04, 0.44), (0.20, 0.38, 0.07)),
            (dog.CREAM, (0, -0.36, 0.33), (0.10, 0.10, 0.13)),
        ]),
        "tail": ([(0, 0.42, 0.33), (0, 0.50, 0.37), (0, 0.57, 0.42), (0, 0.62, 0.48), (0, 0.65, 0.54)], 0.045,
                 [(dog.SADDLE, 2, (0.08, 0.08, 0.08))]),
        "shoulder": (0, -0.22, 0.32),
        "hip": (0, 0.32, 0.31),
        "neck": ((0, -0.35, 0.42), (0, -0.40, 0.51)),
        "head": ("nova", (0, -0.43, 0.43), 1.25),
        "scale": 0.88,
        "fur": ((0.032, 7000, 0.8), (0.09, 9000, 0.7)),
        "fur_style": "silky",
        # Her head is big for her short legs: sitting, she rears her chest up
        # with her head level, so her front legs show under her ears; lying,
        # her head rests higher
        "poses": {"sit": {"chest": (10, 0, 0), "neck": (4, 0, 0)},
                  "lie": {"neck": (-28, 12, -34)}},
    },
    # Millie: a sturdy tri-colour hound puppy, black with a white bib and tan
    # legs, in her captain's hat (dog.millie_head)
    "millie": {
        "torso": [
            ((0, -0.14, 0.40), (0.16, 0.17, 0.16)),
            ((0, 0.03, 0.40), (0.15, 0.18, 0.15)),
            ((0, 0.20, 0.41), (0.15, 0.15, 0.15)),
            ((0, -0.27, 0.51), (0.15, 0.14, 0.17), (-30, 0, 0)),
        ],
        "front": (0.09, -0.16, 0.39),
        "hind": (0.095, 0.21, 0.39),
        "leg": 1.15,
        # Black (lifted a little, so she doesn't vanish into the watch's black)
        # with a white bib and belly and tan legs
        "coat": (SADDLE_BLACK, [
            (dog.WHITE, (0, -0.36, 0.44), (0.12, 0.12, 0.24)),
            (dog.WHITE, (0, -0.02, 0.27), (0.12, 0.22, 0.06)),
            (dog.TAN, (-0.09, -0.16, 0.20), (0.10, 0.10, 0.24)),
            (dog.TAN, (0.09, -0.16, 0.20), (0.10, 0.10, 0.24)),
            (dog.TAN, (-0.10, 0.21, 0.22), (0.10, 0.11, 0.15)),
            (dog.TAN, (0.10, 0.21, 0.22), (0.10, 0.11, 0.15)),
        ]),
        "socks": dog.WHITE,
        "tail": ([(0, 0.30, 0.45), (0, 0.35, 0.53), (0, 0.37, 0.62), (0, 0.36, 0.70)], 0.05,
                 [(SADDLE_BLACK, 1, (0.08, 0.08, 0.08)), (dog.WHITE, 3, (0.06, 0.06, 0.07))]),
        "shoulder": (0, -0.14, 0.42),
        "hip": (0, 0.23, 0.41),
        "neck": ((0, -0.26, 0.55), (0, -0.32, 0.65)),
        # Her head sits high enough that her neck shows, and low enough that
        # her hat clears the top of the watch's dog box
        "head": ("millie", (0, -0.31, 0.635), 1.3),
        "fur": ((0.035, 7000, 0.5), (0.04, 9000, 0.2)),
        "fur_style": "fluffy",
        # Lying, her tail curls up behind her
        "poses": {"lie": {"tail0": (-20, 0, 40), "tail1": (-35, 0, 10), "tail2": (-15, 0, 0)}},
        # The Zzz rise clear of her hat
        "zzz": (0.12, -0.4, 0.86),
    },
}


# --- building ---------------------------------------------------------------

def leg_elements(spec):
    """Four legs from the attachment points: upper leg, lower leg and paw,
    with the hind legs' thicker thighs and angled hocks."""
    t = spec["leg"]
    fx, fy, fh = spec["front"]
    hx, hy, hh = spec["hind"]
    elements, patches = [], []
    socks = spec.get("socks")
    for side in (-1, 1):
        x = side * fx
        elements += [((x, fy, fh * 0.76), (0.055 * t, 0.06 * t, fh * 0.24)),
                     ((x, fy - 0.01, fh * 0.38), (0.04 * t, 0.04 * t, fh * 0.26)),
                     ((x, fy - 0.04, 0.03), (0.05 * t, 0.07 * t, 0.03))]
        x = side * hx
        elements += [((x, hy, hh * 0.76), (0.075 * t, 0.11 * t, hh * 0.31)),
                     ((x, hy + 0.035, hh * 0.36), (0.04 * t, 0.045 * t, hh * 0.24), (-12, 0, 0)),
                     ((x, hy, 0.03), (0.05 * t, 0.07 * t, 0.03))]
        if socks:
            patches += [(socks, (side * fx, fy, fh * 0.29), (0.08, 0.09, fh * 0.4)),
                        (socks, (side * hx, hy + 0.02, hh * 0.17), (0.08, 0.10, hh * 0.29))]
    return elements, patches


def bones(spec):
    """The skeleton, from the spec's proportions: (name, head, tail, parent)."""
    fx, fy, fh = spec["front"]
    hx, hy, hh = spec["hind"]
    shoulder, hip = spec["shoulder"], spec["hip"]
    neck_base, neck_top = spec["neck"]
    mid = Vector(shoulder).lerp(Vector(hip), 0.5)
    tail_points = spec["tail"][0]
    out = [
        ("body", (0, mid.y, mid.z - 0.14), (0, mid.y, mid.z - 0.04), None),
        # The spine pivots at the shoulders, so sitting drops the hips
        ("spine", shoulder, hip, "body"),
        ("chest", shoulder, neck_base, "spine"),
        ("neck", neck_base, neck_top, "chest"),
    ]
    for i in range(len(tail_points) - 1):
        out.append((f"tail{i}", tail_points[i], tail_points[i + 1], "spine" if i == 0 else f"tail{i - 1}"))
    for s, side in (("L", -1), ("R", 1)):
        x = side * fx
        out += [
            (f"front_upper.{s}", (x, fy, fh), (x, fy, fh * 0.52), "spine"),
            (f"front_lower.{s}", (x, fy, fh * 0.52), (x, fy - 0.015, fh * 0.14), f"front_upper.{s}"),
            (f"front_foot.{s}", (x, fy - 0.015, fh * 0.14), (x, fy - 0.065, 0.02), f"front_lower.{s}"),
        ]
        x = side * hx
        out += [
            (f"thigh.{s}", (x, hy, hh), (x, hy + 0.035, hh * 0.52), "spine"),
            (f"shin.{s}", (x, hy + 0.035, hh * 0.52), (x, hy + 0.02, hh * 0.17), f"thigh.{s}"),
            (f"hind_foot.{s}", (x, hy + 0.02, hh * 0.17), (x, hy - 0.03, 0.02), f"shin.{s}"),
        ]
    return out


LEGS = {("front", s): (f"front_upper.{s}", f"front_lower.{s}", f"front_foot.{s}") for s in "LR"}
LEGS.update({("hind", s): (f"thigh.{s}", f"shin.{s}", f"hind_foot.{s}") for s in "LR"})


def build_armature(root, spec):
    data = bpy.data.armatures.new("skeleton")
    arm = bpy.data.objects.new("skeleton", data)
    dog.link(arm, root)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent in bones(spec):
        b = data.edit_bones.new(name)
        b.head, b.tail, b.roll = head, tail, 0
        if parent:
            b.parent = data.edit_bones[parent]
            b.use_connect = (Vector(head) - data.edit_bones[parent].tail).length < 1e-6
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    return arm


def bind(mesh, arm):
    """Automatic (bone heat) weights, like Ctrl+P > With Automatic Weights."""
    for o in bpy.context.selected_objects:
        o.select_set(False)
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")


def parent_to_bone(obj, arm, bone):
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    bpy.context.view_layer.update()
    obj.matrix_world = world


# Coat textures on top of fur length and density: how strands clump into
# locks, wave, frizz, how thick they are and how glossy.
FUR_STYLES = {
    # Short and coarse with a bit of shine, like a cattle dog's double coat
    "coarse": {"clump": 0.25, "clump_shape": 0.1, "frizz": 0.15, "wave": 0.0, "thickness": 0.0019,
               "roughness": 0.5, "radial": 0.7},
    # Long, glossy and wavy, falling in locks
    "silky": {"clump": 0.5, "clump_shape": -0.3, "frizz": 0.08, "wave": 0.012, "thickness": 0.0013,
              "roughness": 0.22, "radial": 0.4},
    # Soft puppy fluff: frizzy, separate, matte
    "fluffy": {"clump": 0.04, "clump_shape": 0.0, "frizz": 0.4, "wave": 0.0, "thickness": 0.0014,
               "roughness": 0.6, "radial": 0.9},
}


def style_fur(obj, style):
    """Apply a FUR_STYLES entry to obj's fur (the particle system dog.add_fur made)."""
    mod = next(m for m in obj.modifiers if m.type == "PARTICLE_SYSTEM")
    settings = mod.particle_system.settings
    length = settings.hair_length
    settings.clump_factor = style["clump"]
    settings.clump_shape = style["clump_shape"]
    settings.roughness_1 = length * style["frizz"]
    settings.roughness_endpoint = length * style["frizz"] * 0.6
    settings.radius_scale = style["thickness"]
    if style["wave"] > 0:
        settings.kink = "WAVE"
        settings.kink_amplitude = style["wave"]
        settings.kink_frequency = 3.0
    hair = bpy.data.materials[settings.material_slot]
    for node in hair.node_tree.nodes:
        if node.type == "BSDF_HAIR_PRINCIPLED":
            node.inputs["Roughness"].default_value = style["roughness"]
            node.inputs["Radial Roughness"].default_value = style["radial"]


HEADS = {
    "ozzie": lambda rig, pivot, ball: dog.ozzie_head(rig, pivot, ball),
    "nova": lambda rig, pivot, ball: dog.nova_head(rig, pivot),
    "millie": lambda rig, pivot, ball: dog.millie_head(rig, pivot),
}


def build_dog(spec):
    """Skin a dog onto the rig. Returns the rig: root (heading and
    position), armature, head pivot, ears, eyes, tongue, and the held ball."""
    root = dog.empty("root", (0, 0, 0))
    root.scale = (spec.get("scale", 1.0),) * 3
    rig = {"root": root, "spec": spec}
    legs, sock_patches = leg_elements(spec)
    base, patches = spec["coat"]
    body = dog.sculpt("body", spec["torso"] + legs, dog.coat_materials("body", base, sock_patches + patches))

    points, radius, tail_patches = spec["tail"]
    tail_elements = []
    for a, b in zip(points, points[1:]):
        for t in (0.0, 0.5):
            tail_elements.append((tuple(Vector(a).lerp(Vector(b), t)), (radius, radius, radius * 1.1)))
    tail_elements.append((points[-1], (radius * 0.9,) * 3))
    tail = dog.sculpt("tail", tail_elements, dog.coat_materials(
        "tail", base, [(c, points[i], r) for c, i, r in tail_patches]))

    head_name, head_loc, head_scale = spec["head"]
    head_pivot = dog.empty("head_pivot", (0, -0.05, 0.95))
    HEADS[head_name](rig, head_pivot, spec.get("ball", False))
    head_pivot.scale = (head_scale,) * 3
    head_pivot.location = head_loc
    rig["head"] = head_pivot

    collar = None
    if "collar" in spec:
        # Round the neck (its base, unless the spec says where), moving with it
        text, radius, tilt, color, *size = spec["collar"]
        base = spec.get("collar_at", spec["neck"][0])
        collar = dog.empty("collar_pivot", base)
        dog.name_collar(text, base, radius, tilt, color, collar, *size)

    arm = build_armature(root, spec)
    bind(body, arm)
    bind(tail, arm)
    parent_to_bone(head_pivot, arm, "neck")
    if collar is not None:
        parent_to_bone(collar, arm, "neck")
    if not dog.ARGS.no_fur:
        body_fur, tail_fur = spec["fur"]
        dog.add_fur(body, body.data.materials[1], *body_fur)
        dog.add_fur(tail, tail.data.materials[1], *tail_fur)
        style = FUR_STYLES[spec.get("fur_style", "coarse")]
        style_fur(body, style)
        style_fur(tail, style)
    rig["arm"] = arm
    return rig


# --- poses ------------------------------------------------------------------

# Bone angles in degrees about each bone's local X (pitch), Y (roll) and
# Z (yaw); "body_loc" moves the whole body (sideways, forward, up). Bones not
# listed are at rest, and the rest pose is standing. For the legs, a negative
# pitch swings the leg forward.
STAND = {}

SIT = {
    "spine": (-42, 0, 0),
    "chest": (40, 0, 0),           # undo the spine's swing: the head stays level
    "neck": (-6, 0, 0),
    "front_upper.L": (42, 0, 0), "front_upper.R": (42, 0, 0),   # front legs stay upright
    "thigh.L": (-42, 0, 14), "thigh.R": (-42, 0, -14),     # haunches splayed so they show beside the chest
    "shin.L": (110, 0, 0), "shin.R": (110, 0, 0),
    "hind_foot.L": (-70, 0, 0), "hind_foot.R": (-70, 0, 0),
    "tail0": (-25, 0, -85), "tail1": (-10, 0, -25), "tail2": (0, 0, -10),   # raised out to her side, so it shows
}

# Lying like a sphinx: body down, front legs out along the ground, hind legs
# tucked and splayed a little, head resting low
LIE = dict(SIT)
LIE.update({
    "body_loc": (0, 0.0, -0.27),
    "spine": (-2, 0, 0),
    "chest": (30, 0, 0),
    "neck": (-10, 12, -34),      # chin low, face turned toward the camera, head tilted
    "front_upper.L": (-86, 0, 0), "front_upper.R": (-86, 0, 0),
    "front_lower.L": (10, 0, 0), "front_lower.R": (10, 0, 0),
    "front_foot.L": (0, 0, 0), "front_foot.R": (0, 0, 0),
    "thigh.L": (-70, 0, 18), "thigh.R": (-70, 0, -18),     # folded close, so long legs don't poke out
    "shin.L": (145, 0, 0), "shin.R": (145, 0, 0),
    "hind_foot.L": (-60, 0, 0), "hind_foot.R": (-60, 0, 0),
    "tail0": (75, 0, 35), "tail1": (35, 0, 25), "tail2": (15, 0, 15),
})

POSES = {"stand": STAND, "sit": SIT, "lie": LIE}


# The leg height the shared poses were made for (Ozzie's)
POSE_LEG = 0.42


# Bones hanging off the spine: when the spine tilts by a different amount,
# these keep their angle to the ground
SPINE_CHILDREN = ("chest", "front_upper.L", "front_upper.R", "thigh.L", "thigh.R", "tail0")


def spine_drop(spec):
    """How far the hips sit below the shoulders' height, and the spine's length."""
    shoulder, hip = Vector(spec["shoulder"]), Vector(spec["hip"])
    return hip.z, (hip - shoulder).length


def sit_tilt(spec):
    """The spine's pitch when sitting: tilted until the hips are as low,
    relative to the hind legs, as Ozzie's (whose proportions SIT was made
    for). A long, low dog like Nova tilts less, or her rump would sink
    through the floor."""
    hip_z, length = spine_drop(spec)
    ref_hip, ref_length = spine_drop(SPECS["ozzie"])
    ratio = (ref_hip - ref_length * math.sin(math.radians(-SIT["spine"][0]))) / SPECS["ozzie"]["hind"][2]
    drop = max(0.0, min(length, hip_z - ratio * spec["hind"][2]))
    return -math.degrees(math.asin(drop / length))


def dog_pose(rig, name):
    """A shared pose with the dog's own adjustments. How far the body drops
    (lying) scales with the dog's leg height, and how far the spine tilts
    (sitting) with the length of the body."""
    spec = rig["spec"]
    pose = dict(POSES[name])
    if "body_loc" in pose:
        x, y, z = pose["body_loc"]
        pose["body_loc"] = (x, y, z * spec["front"][2] / POSE_LEG)
    if name == "sit":
        tilt = sit_tilt(spec)
        change = pose["spine"][0] - tilt
        pose["spine"] = (tilt, 0, 0)
        for bone in SPINE_CHILDREN:
            p, r, y = pose.get(bone, (0, 0, 0))
            pose[bone] = (p + change, r, y)
    pose.update(spec["poses"].get(name, {}))
    return pose


def blend(a, b, t):
    """Pose a moved toward pose b by t (0-1)."""
    out = {}
    for name in set(a) | set(b):
        va = a.get(name, (0, 0, 0))
        vb = b.get(name, (0, 0, 0))
        out[name] = tuple(x + (y - x) * t for x, y in zip(va, vb))
    return out


def add(pose, offsets):
    out = dict(pose)
    for name, v in offsets.items():
        base = out.get(name, (0, 0, 0))
        out[name] = tuple(x + y for x, y in zip(base, v))
    return out


def ease(a, b, x):
    """0 before frame a, 1 after frame b, easing in and out between."""
    return dog.smoothstep(a, b, x)


# Walk: legs move in the order left hind, left front, right hind, right front.
# The phase counts strides (1.0 per cycle) by distance, so the feet don't slide.
WALK_PHASES = {("hind", "L"): 0.0, ("front", "L"): 0.25, ("hind", "R"): 0.5, ("front", "R"): 0.75}
STRIDE = 0.30               # ground covered per cycle
WALK_SPEED = 0.03           # units per frame at full speed: a stride every 10 frames


def walk_offsets(phase, amount):
    """The walk cycle at `phase`, scaled by `amount` (0 standing, 1 walking)."""
    off = {}
    for leg, (upper, lower, foot) in LEGS.items():
        p = 2 * math.pi * (phase + WALK_PHASES[leg])
        swing = 22 * math.sin(p)
        # The leg folds while it swings forward (cos < 0) so the paw clears the ground
        lift = max(0.0, -math.cos(p))
        if leg[0] == "front":
            off[upper] = (swing * amount, 0, 0)
            off[lower] = (-38 * lift * amount, 0, 0)
            off[foot] = (30 * lift * amount, 0, 0)
        else:
            off[upper] = (swing * amount, 0, 0)
            off[lower] = (40 * lift * amount, 0, 0)
            off[foot] = (-30 * lift * amount, 0, 0)
    bob = 2 * math.pi * 2 * phase
    off["body_loc"] = (0, 0, 0.012 * math.cos(bob) * amount)
    off["spine"] = (0, 2.5 * math.sin(2 * math.pi * phase) * amount, 0)
    # Head carried a little lower while walking, nodding with each step
    off["neck"] = ((10 + 3 * math.sin(bob + 0.6)) * amount, 0, 0)
    off["tail0"] = (0, 0, 14 * math.sin(2 * math.pi * phase) * amount)
    off["tail1"] = (0, 0, 10 * math.sin(2 * math.pi * phase - 0.6) * amount)
    return off


# --- keying -----------------------------------------------------------------

def key_pose(rig, pose, frame):
    arm = rig["arm"]
    for pb in arm.pose.bones:
        angles = pose.get(pb.name, (0, 0, 0))
        pb.rotation_euler = [math.radians(a) for a in angles]
        pb.keyframe_insert("rotation_euler", frame=frame)
    # The body bone points up, so up is along its local Y
    x, y, z = pose.get("body_loc", (0, 0, 0))
    body = arm.pose.bones["body"]
    body.location = (x, z, y)
    body.keyframe_insert("location", frame=frame)


def key_root(rig, frame, position, heading):
    root = rig["root"]
    root.location = (position.x, position.y, 0)
    root.rotation_euler = (0, 0, math.radians(heading))
    root.keyframe_insert("location", frame=frame)
    root.keyframe_insert("rotation_euler", frame=frame)


def key_face(rig, frame, blink=1.0, ear=0.0, tongue=False):
    for eye in rig["eyes"]:
        eye.scale = (1, 1, blink)
        eye.keyframe_insert("scale", frame=frame)
    for i, e in enumerate(rig["ears"]):
        e.rotation_euler = (0, math.radians(ear * (1 if i else -1)), 0)
        e.keyframe_insert("rotation_euler", frame=frame)
    rig["tongue"].hide_render = not tongue
    rig["tongue"].keyframe_insert("hide_render", frame=frame)


def show(obj, frame, visible):
    obj.hide_render = not visible
    obj.keyframe_insert("hide_render", frame=frame)


# Behind the camera: out of sight but still in the scene. Objects that appear
# mid-render make Cycles compile their shaders mid-render, which can crash
# the Metal shader cache, so the loose ball waits here instead of hiding.
OFFSTAGE = Vector((0, -12, 0))


def fcurves(obj):
    """An object's animation curves (Blender 5 keeps them in slotted actions)."""
    anim = obj.animation_data
    from bpy_extras import anim_utils
    return anim_utils.action_get_channelbag_for_slot(anim.action, anim.action_slot).fcurves


def hold(obj, frame, location):
    """Put obj at `location` from `frame`, holding there (not sliding) until
    its next key, so motion blur doesn't streak it across the frame."""
    obj.location = location
    obj.keyframe_insert("location", frame=frame)
    for curve in fcurves(obj):
        if curve.data_path == "location":
            for k in curve.keyframe_points:
                if abs(k.co.x - frame) < 0.5:
                    k.interpolation = "CONSTANT"


def park(obj, frame):
    """Move obj off stage from `frame`."""
    hold(obj, frame, OFFSTAGE)


def forward(heading):
    """The facing direction on the ground for a root heading (0 faces -Y)."""
    h = math.radians(heading)
    return Vector((math.sin(h), -math.cos(h), 0))


# --- the ball ---------------------------------------------------------------

BALL_R = 0.085
GRAVITY = 23.0          # units/s^2: a 0.5 m dog is about 1.2 units tall
RESTITUTION = 0.58      # a tennis ball on a soft floor
BOUNCE_FRICTION = 0.88  # horizontal speed kept through each bounce
ROLL_DRAG = 1.6         # units/s^2 of rolling resistance
SETTLE = 0.4            # below this falling speed it stops bouncing and rolls


def steer_ball(path, rest):
    """The simulated path eased, from nothing at the drop to all of it at the
    end, so the ball comes to rest at `rest` (on the ground)."""
    end = path[-1][0]
    shift = Vector((rest.x - end.x, rest.y - end.y, 0))
    last = len(path) - 1
    return [(p + shift * dog.smoothstep(0, last, i), angle, axis, squash)
            for i, (p, angle, axis, squash) in enumerate(path)]


def simulate_ball(start, velocity, frames):
    """A dropped ball, sub-stepped at 1 kHz so bounces land between frames:
    falls, bounces lower each time, loses a little speed at each bounce, then
    rolls to a stop. Returns per frame (position, roll angle, axis, squash)."""
    dt = 0.001
    steps = int(1 / (FPS * dt))
    p, v = Vector(start), Vector(velocity)
    angle = 0.0
    out = []
    for _ in range(frames):
        squash = 1.0
        for _ in range(steps):
            v.z -= GRAVITY * dt
            p += v * dt
            if p.z <= BALL_R and v.z < 0:
                p.z = BALL_R
                if -v.z > SETTLE:
                    squash = min(squash, max(0.85, 1 - (-v.z) * 0.025))
                    v.z = -v.z * RESTITUTION
                    v.x *= BOUNCE_FRICTION
                    v.y *= BOUNCE_FRICTION
                else:
                    v.z = 0.0
            if v.z == 0.0 and p.z <= BALL_R + 1e-4:
                v.z = 0.0
                p.z = BALL_R
                speed = v.xy.length
                if speed > 0:
                    slow = max(0.0, speed - ROLL_DRAG * dt)
                    v.x *= slow / speed
                    v.y *= slow / speed
            angle += v.xy.length * dt / BALL_R
        axis = Vector((-v.y, v.x, 0)).normalized() if v.xy.length > 1e-6 else None
        out.append((p.copy(), angle, axis, squash))
    return out


def held_ball_position(rig, frame):
    """Where the carried ball's centre is at `frame`. Sculpts keep their
    origin where they were built, so it's the centre, not the origin, that
    gets transformed."""
    bpy.context.scene.frame_set(frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    return rig["ball"].evaluated_get(depsgraph).matrix_world @ rig["ball_centre"]


def key_loose_ball(ball, frames, start_frame):
    """Key the loose ball along a simulated path, rolling the right way."""
    last_axis = Vector((1, 0, 0))
    ball.rotation_mode = "AXIS_ANGLE"
    for i, (p, angle, axis, squash) in enumerate(frames):
        f = start_frame + i
        ball.location = p - Vector((0, 0, BALL_R * (1 - squash)))
        if axis is not None:
            last_axis = axis
        ball.rotation_axis_angle = (angle, *last_axis)
        ball.scale = (1 / math.sqrt(squash), 1 / math.sqrt(squash), squash)
        for path in ("location", "rotation_axis_angle", "scale"):
            ball.keyframe_insert(path, frame=f)


# --- timelines --------------------------------------------------------------

SIT_SPOT = Vector((0.0, 0.04, 0))
SIT_HEADING = 6          # sitting nearly square to the camera, looking out of the watch
LIE_HEADING = -62        # lying turned to the left, so her length shows
LIE_SPOT = SIT_SPOT + Vector((0.26, 0.24, 0))   # and shuffled right and back, so she fits the box
WALK_HEADING = 80        # nearly side-on while walking
DROP_TOSS = Vector((0, 0, 0.3))
DROP_SPEED = 0.15        # units/s as the ball leaves her mouth
DROP_ANGLE = 50          # degrees to her left of straight ahead: rolls out across the screen
# Where the ball comes to rest, just in front of her paws: facing the camera,
# it would roll so far forward that it drops out of the bottom of the box
BALL_REST = Vector((0.10, -0.50, 0))


# The watch's layout, in pixels (see DogLayout and tools/build_art.sh): the
# loops are cropped to CROP (left, top, width, in 400px-frame units, so
# whatever size was rendered) and scaled to DOG_BOX_WIDTH at DOG_AT on the
# SCREEN. The walks fill the whole screen instead, so the dog can come and go
# off its edge.
SCREEN = 416
DOG_AT = (97, 134)
DOG_BOX_WIDTH = 222
CROP = (76, 62, 292)


def frame_full_face(scene, size):
    """Widen the view to the whole watch screen, keeping the dog exactly where
    the loops' crop puts her, so a walk-in ends on the loops' first frame."""
    scale = DOG_BOX_WIDTH / CROP[2]     # screen px per 400px-frame px
    width = SCREEN / scale              # the screen, in 400px-frame px
    left = CROP[0] - DOG_AT[0] / scale
    top = CROP[1] - DOG_AT[1] / scale
    cam = scene.camera.data
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width *= width / 400
    # Shifts are fractions of the frame width, y up
    cam.shift_x = (left + width / 2 - 200) / width
    cam.shift_y = (200 - top - width / 2) / width
    scene.render.resolution_x = scene.render.resolution_y = round(size * width / 400)


def walk_path(speeds, headings, end):
    """Positions for each frame from per-frame speeds and headings, ending at `end`."""
    pos = [Vector((0, 0, 0))]
    for i in range(1, len(speeds)):
        pos.append(pos[-1] + forward(headings[i]) * speeds[i])
    shift = end - pos[-1]
    return [p + shift for p in pos]


# Turning, a dog's feet keep stepping: her body sweeps this much ground per
# degree of turn, on top of walking, so she steps round instead of spinning
# on the spot. Her head turns into a turn this many frames ahead of her body.
TURN_STEP = 0.004
HEAD_LEAD = 6


def gait(speeds, headings):
    """Per frame, the walk cycle's phase and how much she's stepping (0-1),
    from the ground her feet cover walking and turning."""
    phase, out = 0.0, []
    for i, speed in enumerate(speeds):
        turn = abs(headings[i] - headings[i - 1]) if i else 0.0
        step = speed + TURN_STEP * turn
        phase += step / STRIDE
        out.append((phase, min(1.0, step / WALK_SPEED * 1.4)))
    return out


def head_lead(headings, f):
    """Her neck turned toward where her body will face in a few frames, so
    her head leads the turn (positive turns left, like the heading)."""
    ahead = headings[min(len(headings), f + HEAD_LEAD) - 1]
    yaw = max(-35.0, min(35.0, 0.7 * (ahead - headings[f - 1])))
    return {"neck": (0, 0, yaw)}


class WalkIn:
    """Walks in (carrying the ball, if she has one), curves round toward the
    camera as she slows, head first, drops the ball, which bounces and rolls,
    then sits and settles on the sitting loops' first frame."""
    # Starts far enough left to be off the watch's screen on frame 1
    FRAMES = 116
    SLOW_FROM, STOP_AT = 70, 86
    TURN_FROM, TURN_TO = 60, 86
    DIP_FROM, DROP_AT, DIP_TO = 85, 89, 94
    SIT_FROM, SIT_TO = 93, 106
    # Trots in, easing to a walk well before she slows, like the walk-out
    TROT_FROM, TROT_TO = 36, 50

    def __init__(self, rig, loose_ball):
        self.rig, self.ball = rig, loose_ball
        n = self.FRAMES
        self.speeds = [WALK_SPEED * (1 + 0.4 * (1 - ease(self.TROT_FROM, self.TROT_TO, f)))
                       * (1 - ease(self.SLOW_FROM, self.STOP_AT, f)) for f in range(1, n + 1)]
        self.headings = [WALK_HEADING + (SIT_HEADING - WALK_HEADING) * ease(self.TURN_FROM, self.TURN_TO, f)
                         for f in range(1, n + 1)]
        self.positions = walk_path(self.speeds, self.headings, SIT_SPOT)
        self.gait = gait(self.speeds, self.headings)

    def pose(self, f):
        phase, amount = self.gait[f - 1]
        pose = add(dog_pose(self.rig, "stand"), walk_offsets(phase, amount))
        pose = add(pose, head_lead(self.headings, f))
        # Dip to drop the ball (if she has one), then look up
        dip = ease(self.DIP_FROM, self.DROP_AT, f) - ease(self.DROP_AT, self.DIP_TO, f)
        dip *= 1 if self.ball is not None else 0
        pose = add(pose, {"neck": (18 * dip, 0, 0), "chest": (4 * dip, 0, 0)})
        sit = ease(self.SIT_FROM, self.SIT_TO, f)
        pose = blend(pose, dog_pose(self.rig, "sit"), sit)
        # A small overshoot of the head as she lands, and the tail sweeping
        settle = dog.pulse(f, self.SIT_TO + 1, 2.0)
        wag = 12 * math.sin((f - self.SIT_FROM) * 0.9) * sit * (1 - ease(self.SIT_TO, self.FRAMES - 2, f))
        pose = add(pose, {"neck": (-5 * settle, 0, 0), "tail1": (0, 0, wag)})
        # Ease into the awake loop's first frame, so the cut to it is seamless
        into_loop = ease(self.SIT_TO, self.FRAMES, f)
        return add(pose, {k: tuple(a * into_loop for a in v) for k, v in awake_offsets(1).items()})

    def animate(self):
        rig = self.rig
        for f in range(1, self.FRAMES + 1):
            key_pose(rig, self.pose(f), f)
            key_root(rig, f, self.positions[f - 1], self.headings[f - 1])
            blink = 0.1 if f in (self.SIT_TO + 4, self.SIT_TO + 5) else 1.0
            ear = 6 * math.sin(f * 0.8) * (1 - ease(self.SIT_FROM, self.SIT_TO, f))
            key_face(rig, f, blink=blink, ear=ear)
        if self.ball is not None:
            start = held_ball_position(rig, self.DROP_AT)
            toss = forward(self.headings[self.DROP_AT - 1] + DROP_ANGLE) * DROP_SPEED + DROP_TOSS
            path = simulate_ball(start, toss, self.FRAMES - self.DROP_AT + 1)
            path = steer_ball(path, BALL_REST)
            park(self.ball, 1)
            key_loose_ball(self.ball, path, self.DROP_AT)
            show(rig["ball"], 1, True)
            show(rig["ball"], self.DROP_AT, False)
            self.ball_rest = path[-1][0]
            print(f"ball dropped at {tuple(round(c, 3) for c in start)}, rests at "
                  f"{tuple(round(c, 3) for c in self.ball_rest)}; dog at {tuple(round(c, 3) for c in SIT_SPOT)}")
        return self.FRAMES


def clear_animation(rig, ball):
    objs = [rig["root"], rig["arm"], rig["tongue"], *rig["eyes"], *rig["ears"]]
    if ball is not None:
        objs += [ball, rig["ball"]]
    for obj in objs:
        obj.animation_data_clear()
    for obj in objs[-2:] if ball is not None else []:
        obj.hide_render = False


def ball_rest(rig, ball):
    """Where the walk-in leaves the ball, for the scenes that follow it."""
    walk = WalkIn(rig, ball)
    walk.animate()
    clear_animation(rig, ball)
    return walk.ball_rest


class WalkOut:
    """Stands up, steps to the ball and picks it up, then sets off, curving
    round head first, and trots off."""
    # Ends once she's trotted off the watch's screen
    FRAMES = 104
    STAND_FROM, STAND_TO = 5, 15
    STEP_FROM, STEP_TO = 14, 24
    DIP_FROM, PICK_AT, DIP_TO = 22, 26, 31
    GRAB_AT = 29             # the ball is in her mouth
    TURN_FROM, TURN_TO = 29, 50
    GO_FROM, GO_TO = 29, 40
    DIP = {"neck": (34, 0, 0), "chest": (6, 0, 0)}

    def __init__(self, rig, loose_ball, rest):
        self.rig, self.ball, self.rest = rig, loose_ball, rest

    def mouth_offset(self):
        """Where her mouth is, relative to her spot, at the bottom of the dip."""
        key_pose(self.rig, add(dog_pose(self.rig, "stand"), self.DIP), 1)
        key_root(self.rig, 1, SIT_SPOT, SIT_HEADING)
        mouth = held_ball_position(self.rig, 1)
        clear_animation(self.rig, self.ball)
        return mouth - SIT_SPOT

    def animate(self):
        rig, n = self.rig, self.FRAMES
        reach = Vector((0, 0, 0))
        if self.ball is not None:
            # A step that brings her mouth down right over the ball
            reach = self.rest - self.mouth_offset() - SIT_SPOT
            reach.z = 0
        headings = [SIT_HEADING + (WALK_HEADING + 10 - SIT_HEADING) * ease(self.TURN_FROM, self.TURN_TO, f)
                    for f in range(1, n + 1)]
        # Picks up to a trot once she's turned, so she's gone by the last frame
        speeds = [WALK_SPEED * (ease(self.GO_FROM, self.GO_TO, f) + 0.4 * ease(self.GO_TO, self.GO_TO + 10, f))
                  for f in range(1, n + 1)]
        positions, travel = [], Vector((0, 0, 0))
        for f in range(1, n + 1):
            travel += forward(headings[f - 1]) * speeds[f - 1]
            positions.append(SIT_SPOT + reach * ease(self.STEP_FROM, self.STEP_TO, f) + travel)
        moved = [(positions[f - 1] - positions[f - 2]).length if f > 1 else 0.0 for f in range(1, n + 1)]
        steps = gait(moved, headings)
        for f in range(1, n + 1):
            phase, amount = steps[f - 1]
            amount *= ease(self.STAND_FROM + 4, self.STAND_TO, f)
            stand = ease(self.STAND_FROM, self.STAND_TO, f)
            pose = blend(dog_pose(rig, "sit"),
                         add(add(dog_pose(rig, "stand"), walk_offsets(phase, amount)), head_lead(headings, f)), stand)
            dip = ease(self.DIP_FROM, self.PICK_AT, f) - ease(self.PICK_AT, self.DIP_TO, f)
            dip *= 1 if self.ball is not None else 0
            pose = add(pose, {k: tuple(a * dip for a in v) for k, v in self.DIP.items()})
            pose = add(pose, {"tail1": (0, 0, 16 * math.sin(f * 1.1) * stand)})
            key_pose(rig, pose, f)
            key_root(rig, f, positions[f - 1], headings[f - 1])
            key_face(rig, f, blink=0.1 if f in (3, 4) else 1.0, ear=5 * math.sin(f * 0.8) * amount)
        if self.ball is not None:
            # The ball lifts into her mouth over a few frames, then the held
            # ball takes over exactly where the loose one is, so it doesn't pop
            hold(self.ball, 1, self.rest)
            hold(self.ball, self.PICK_AT - 1, self.rest)
            for f in range(self.PICK_AT, self.GRAB_AT):
                t = ease(self.PICK_AT - 1, self.GRAB_AT, f)
                self.ball.location = self.rest.lerp(held_ball_position(rig, f), t)
                self.ball.keyframe_insert("location", frame=f)
            park(self.ball, self.GRAB_AT)
            show(rig["ball"], 1, False)
            show(rig["ball"], self.GRAB_AT, True)
        return n


# Where the sleeping Zzz rise from, clear of the head; a spec's "zzz" overrides it
ZZZ_FROM = (0.02, -0.4, 0.74)


def awake_offsets(f):
    """The awake loop's movement at frame f: a head tilt, the tail and breathing."""
    tilt = 12 * max(0.0, dog.wave(f, 1)) ** 1.5
    return {"neck": (0, tilt, 0), "tail1": (0, 0, 22 * dog.wave(f, 3)), "tail2": (0, 0, 14 * dog.wave(f, 3, 0.1)),
            "chest": (1.5 * dog.wave(f, 1), 0, 0)}


def idle(rig, mood, zzz):
    """30-frame loops in the resting pose: sitting (awake, happy) or lying
    (sleepy, head down on her paws)."""
    base = dog_pose(rig, "lie" if mood == "sleepy" else "sit")
    for f in range(1, LOOP + 1):
        if mood == "awake":
            off = awake_offsets(f)
            key_face(rig, f, blink=0.1 if f in (19, 20) else 1.0, ear=-0.6 * off["neck"][1])
        elif mood == "happy":
            off = {"body_loc": (0, 0, 0.022 * abs(dog.wave(f, 2))), "neck": (0, 4 * dog.wave(f, 2), 0),
                   "tail0": (0, 0, 18 * dog.wave(f, 5)), "tail1": (0, 0, 28 * dog.wave(f, 5, 0.08)),
                   "tail2": (0, 0, 20 * dog.wave(f, 5, 0.16))}
            key_face(rig, f, blink=0.1 if f in (12, 13) else 1.0, ear=4 * dog.wave(f, 2), tongue=True)
        else:
            breath = dog.wave(f, 1)
            off = {"chest": (2.5 * breath, 0, 0), "spine": (-1.5 * breath, 0, 0), "neck": (2 * breath, 0, 0),
                   "body_loc": (0, 0, 0.008 * breath),
                   "tail2": (0, 0, 10 * (dog.pulse(f, 19, 1.4) - 0.6 * dog.pulse(f, 22, 1.4)))}
            key_face(rig, f, blink=0.06, ear=18 * dog.pulse(f, 9, 1.2))
        key_pose(rig, add(base, off), f)
        if mood == "sleepy":
            key_root(rig, f, LIE_SPOT, LIE_HEADING)
        else:
            key_root(rig, f, SIT_SPOT, SIT_HEADING)
    for i, z in enumerate(zzz):
        z.hide_render = mood != "sleepy"
        for f in range(1, LOOP + 1):
            t = ((f - 1) / LOOP + i / 3) % 1.0
            x, y, zz = rig["spec"].get("zzz", ZZZ_FROM)
            dog.key(z, "location", f, (x + 0.2 * t, y, zz + 0.45 * t))
            s = (0.10 + 0.10 * t) * min(1.0, t * 4, (1 - t) * 4)
            dog.key(z, "scale", f, (s, s, s))
    return LOOP


def lie_down(rig):
    """From sitting to lying, for the dog who stays the night: a yawn, then
    down, turning as she goes, eyes closing, ending on the sleepy loop's first
    frame."""
    sit, lie = dog_pose(rig, "sit"), dog_pose(rig, "lie")
    for f in range(1, LOOP + 1):
        t = ease(6, 24, f)
        yawn = dog.pulse(f, 5, 2.0)
        key_pose(rig, add(blend(sit, lie, t), {"neck": (-18 * yawn, 0, 0)}), f)
        key_root(rig, f, SIT_SPOT.lerp(LIE_SPOT, t), SIT_HEADING + (LIE_HEADING - SIT_HEADING) * t)
        key_face(rig, f, blink=1.0 - 0.94 * ease(18, 28, f), ear=10 * t, tongue=yawn > 0.5)
    return LOOP


def pose_sheet(rig):
    """Key poses side-on and three-quarter, one per frame, for checking a dog."""
    frames = [("stand", 85), ("sit", 85), ("sit", SIT_HEADING), ("lie", 85), ("lie", LIE_HEADING)]
    for i, (name, heading) in enumerate(frames, 1):
        key_pose(rig, dog_pose(rig, name), i)
        key_root(rig, i, SIT_SPOT, heading)
    for i, p in enumerate((0.0, 0.25, 0.5, 0.75), len(frames) + 1):
        key_pose(rig, add(dog_pose(rig, "stand"), walk_offsets(p, 1)), i)
        key_root(rig, i, SIT_SPOT, 85)
    return len(frames) + 4


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--dog", choices=sorted(SPECS), default="ozzie")
    p.add_argument("--anim", choices=["walkin", "walkout", "awake", "happy", "sleepy", "liedown", "poses"],
                   default="poses")
    p.add_argument("--out", help="directory for the PNG frames (a file with --still)")
    p.add_argument("--still", type=int, help="render only this frame")
    p.add_argument("--size", type=int, default=400)
    p.add_argument("--samples", type=int, default=40)
    p.add_argument("--no-fur", action="store_true")
    p.add_argument("--blend", help="also save the .blend file here")
    return p.parse_args(argv)


def main():
    args = parse_args()
    dog.ARGS = args
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Every frame is keyed, so linear keys reproduce the curves exactly
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    dog.setup_scene(args.size, args.samples)
    scene = bpy.context.scene
    spec = SPECS[args.dog]
    rig = build_dog(spec)
    dog.build_ground(ball=False)
    ball = dog.tennis_ball((0, 0, BALL_R), BALL_R) if spec.get("ball") else None
    zzz = dog.build_zzz()
    for z in zzz:
        z.hide_render = True
    rig["tongue"].hide_render = True

    if args.anim == "walkin":
        frames = WalkIn(rig, ball).animate()
    elif args.anim == "walkout":
        frames = WalkOut(rig, ball, ball_rest(rig, ball) if ball else None).animate()
    else:
        if ball is not None:
            ball.location = ball_rest(rig, ball)
            rig["ball"].hide_render = True
        if args.anim in ("awake", "happy", "sleepy"):
            frames = idle(rig, args.anim, zzz)
        elif args.anim == "liedown":
            frames = lie_down(rig)
        else:
            if ball is not None:
                ball.hide_render = True
            frames = pose_sheet(rig)

    scene.frame_start, scene.frame_end = 1, frames
    if args.anim in ("walkin", "walkout"):
        frame_full_face(scene, args.size)
        # Motion blur smooths the walk and the bouncing ball at 10 fps
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = 0.2   # longer smears furry legs into mush
    if args.blend:
        bpy.ops.wm.save_as_mainfile(filepath=args.blend)
    if args.still:
        scene.frame_set(args.still)
        scene.render.filepath = args.out
        bpy.ops.render.render(write_still=True)
    elif args.out:
        scene.render.filepath = args.out.rstrip("/") + "/"
        bpy.ops.render.render(animation=True)


main()
