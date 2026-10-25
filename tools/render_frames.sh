#!/bin/sh
# Render every dog's mood animations with Blender (about 4-5 minutes each) into
# build/frames/<dog>/<mood>/. DOGS and MOODS narrow it down, e.g.
#   DOGS=nova MOODS=happy tools/render_frames.sh
set -e
cd "$(dirname "$0")/.."
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
for dog in ${DOGS:-puppy nova ozzie}; do
    for mood in ${MOODS:-awake happy sleepy}; do
        out="build/frames/$dog/$mood"
        rm -rf "$out"
        "$BLENDER" --background --python tools/blender/dog.py -- --dog "$dog" --mood "$mood" --out "$out" \
            --size 400 --samples 40 > "build/render_${dog}_$mood.log" 2>&1
        echo "rendered $dog $mood: $(ls "$out" | wc -l | tr -d ' ') frames"
    done
done
