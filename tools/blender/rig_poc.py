"""Proof of concept: Ozzie as one skinned mesh on an armature, sitting down.

Reuses dog.py's materials, head and scene, but builds the body and legs as a
single sculpt bound to bones (automatic weights), so a pose change is a real
bend at the joints instead of a cut between two sculpts.

    Blender --background --python tools/blender/rig_poc.py -- --out build/frames/rig_poc [--no-fur]
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Load dog.py's helpers without running its main()
src = (Path(__file__).parent / "dog.py").read_text().replace("ARGS = parse_args()\nmain()", "")
exec(compile(src, "dog.py", "exec"))
ARGS = parse_args()

SIT_FROM, SIT_TO = 7, 21   # frames: stand, sit down, then hold
TURN = 40                  # degrees, three-quarter view so the sit reads
SIT = 1.0


def build_body():
    """Ozzie standing (from ozzie_standing) with the legs melted into the body."""
    elements = [
        ((0, -0.15, 0.43), (0.15, 0.17, 0.16)),
        ((0, 0.03, 0.43), (0.14, 0.18, 0.14)),
        ((0, 0.21, 0.44), (0.14, 0.15, 0.14)),
        ((0, -0.29, 0.56), (0.11, 0.12, 0.15), (-30, 0, 0)),
    ]
    patches = [
        (DARK_RED, (0, 0.05, 0.57), (0.18, 0.32, 0.08)),
        (WHITE, (0, -0.30, 0.44), (0.10, 0.10, 0.15)),
        (WHITE, (0, -0.02, 0.29), (0.12, 0.24, 0.06)),
    ]
    for side in (-1, 1):
        x, y = side * 0.085, -0.17
        elements += [((x, y, 0.32), (0.055, 0.06, 0.10)),
                     ((x, y - 0.01, 0.16), (0.04, 0.04, 0.11)),
                     ((x, y - 0.04, 0.03), (0.05, 0.07, 0.03))]
        patches.append((WHITE, (x, y, 0.12), (0.08, 0.09, 0.17)))
        x, y = side * 0.09, 0.22
        elements += [((x, y, 0.32), (0.07, 0.10, 0.12)),
                     ((x, y + 0.04, 0.15), (0.04, 0.045, 0.10), (-12, 0, 0)),
                     ((x, y + 0.01, 0.03), (0.05, 0.07, 0.03))]
        patches.append((WHITE, (x, y + 0.02, 0.07), (0.08, 0.10, 0.12)))
    # No fur yet: it goes on after binding so it rides on the deformed mesh
    return sculpt("body", elements, coat_materials("body", RED, patches))


# Bones in rest-pose coordinates: (name, head, tail, parent)
BONES = [
    ("spine", (0, -0.15, 0.45), (0, 0.24, 0.44), None),        # pivots at the shoulders
    ("chest", (0, -0.15, 0.45), (0, -0.30, 0.60), "spine"),
    ("tail", (0, 0.33, 0.48), (0, 0.40, 0.66), "spine"),
]
for s, side in (("L", -1), ("R", 1)):
    BONES += [
        (f"front_upper.{s}", (side * 0.085, -0.17, 0.42), (side * 0.085, -0.17, 0.22), "spine"),
        (f"front_lower.{s}", (side * 0.085, -0.17, 0.22), (side * 0.085, -0.20, 0.02), f"front_upper.{s}"),
        (f"thigh.{s}", (side * 0.09, 0.22, 0.42), (side * 0.09, 0.25, 0.22), "spine"),
        (f"shin.{s}", (side * 0.09, 0.25, 0.22), (side * 0.09, 0.23, 0.02), f"thigh.{s}"),
    ]


def build_armature(root):
    data = bpy.data.armatures.new("skeleton")
    arm = bpy.data.objects.new("skeleton", data)
    link(arm, root)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent in BONES:
        b = data.edit_bones.new(name)
        b.head, b.tail, b.roll = head, tail, 0
        if parent:
            b.parent = data.edit_bones[parent]
            b.use_connect = Vector(head) == data.edit_bones[parent].tail
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


def sit_pose(t):
    """Bone rotations (degrees about each bone's local X) at sit amount t."""
    tilt = 42 * t                      # back end drops as the spine swings round the shoulders
    return {
        "spine": -tilt,
        # Undo most of the spine's swing so the head stays nearly level
        "chest": tilt * 0.95,
        "tail": 35 * t,
        "front_upper.L": tilt, "front_upper.R": tilt,     # front legs stay upright
        "front_lower.L": 0, "front_lower.R": 0,
        "thigh.L": tilt - 75 * t, "thigh.R": tilt - 75 * t,
        "shin.L": 110 * t, "shin.R": 110 * t,
    }


def animate_sit(arm, head_pivot):
    for f in range(1, FRAMES + 1):
        t = smoothstep(SIT_FROM, SIT_TO, f)
        for name, deg in sit_pose(t).items():
            key(arm.pose.bones[name], "rotation_euler", f, (math.radians(deg), 0, 0))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    setup_scene(ARGS.size, ARGS.samples)
    root = empty("root", (0, 0, 0))
    rig = {"root": root}
    body = build_body()
    tail_root = empty("tail_root", (0, 0.33, 0.48))
    base = Vector(tail_root.location)
    steps = [(0, 0.0, 0.0), (0, 0.05, 0.04), (0, 0.08, 0.10), (0, 0.08, 0.16),
             (0, 0.05, 0.21), (0, 0.0, 0.24), (0, -0.04, 0.24), (0, -0.07, 0.22)]
    tail = [(tuple(base + Vector(d)), (0.055, 0.055, 0.06)) for d in steps]
    sculpt("tail", tail, coat_materials("tail", RED, [(WHITE, tuple(base + Vector(steps[7])), (0.07, 0.07, 0.06))]),
           tail_root, fur=(0.06, 9000, 0.3))
    head_pivot = empty("head_pivot", (0, -0.05, 0.95))
    ozzie_head(rig, head_pivot, ball=False)
    head_pivot.scale = (1.25,) * 3
    head_pivot.location = (0, -0.36, 0.66)
    rig["tongue"].hide_render = True

    arm = build_armature(root)
    bind(body, arm)
    parent_to_bone(head_pivot, arm, "chest")
    parent_to_bone(tail_root, arm, "tail")
    if not ARGS.no_fur:
        add_fur(body, body.data.materials[1], 0.03, 7000, 0.5)
    root.rotation_euler = (0, 0, math.radians(TURN))
    build_ground(ball=False)
    animate_sit(arm, head_pivot)

    scene = bpy.context.scene
    if ARGS.blend:
        bpy.ops.wm.save_as_mainfile(filepath=ARGS.blend)
    if ARGS.still:
        scene.frame_set(SIT_TO)
        scene.render.filepath = ARGS.still
        bpy.ops.render.render(write_still=True)
    elif ARGS.out:
        scene.render.filepath = ARGS.out.rstrip("/") + "/"
        bpy.ops.render.render(animation=True)


main()
