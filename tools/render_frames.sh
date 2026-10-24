#!/bin/sh
# Render every mood's animation frames with Blender (about 4 minutes per mood).
set -e
cd "$(dirname "$0")/.."
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
for mood in ${MOODS:-awake happy sleepy}; do
    rm -rf "build/frames/$mood"
    "$BLENDER" --background --python tools/blender/dog.py -- --mood "$mood" --out "build/frames/$mood" \
        --size 400 --samples 40 > "build/render_$mood.log" 2>&1
    echo "rendered $mood: $(ls build/frames/$mood | wc -l | tr -d ' ') frames"
done
