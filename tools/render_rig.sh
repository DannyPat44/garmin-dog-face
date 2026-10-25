#!/bin/sh
# Render dogs on the shared skeleton (tools/blender/dog_rig.py) into
# build/frames/rig/<dog>/<anim>/. DOGS and ANIMS narrow it down, e.g.
#   DOGS=ozzie ANIMS="walkin walkout" tools/render_rig.sh
# SIZE (default 400) and SAMPLES (default 40) trade quality for time.
set -e
cd "$(dirname "$0")/.."
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
for dog in ${DOGS:-ozzie}; do
    for anim in ${ANIMS:-walkin walkout awake happy sleepy liedown}; do
        out="build/frames/rig/$dog/$anim"
        rm -rf "$out"
        "$BLENDER" --background --python tools/blender/dog_rig.py -- --dog "$dog" --anim "$anim" --out "$out" \
            --size "${SIZE:-400}" --samples "${SAMPLES:-40}" > "build/render_rig_${dog}_$anim.log" 2>&1
        echo "rendered $dog $anim: $(ls "$out" | wc -l | tr -d ' ') frames"
    done
done
