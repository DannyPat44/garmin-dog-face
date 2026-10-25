#!/bin/sh
# Watch-size review GIFs of the skeleton renders (tools/render_rig.sh):
#   build/review/rig_<dog>_<anim>.gif  each animation
#   build/review/rig_<dog>_story.gif   walk in, sit for two loops, walk out
set -e
cd "$(dirname "$0")/.."
CROP=292:328:76:62
FPS=10
mkdir -p build/review
gif() {  # gif <out> <frame dirs...>: frames flattened onto black, cropped and scaled like the watch art
    out=$1
    shift
    list=build/review/.frames.txt
    : > "$list"
    for dir in "$@"; do
        for f in "$dir"/*.png; do echo "file '$PWD/$f'" >> "$list"; echo "duration 0.1" >> "$list"; done
    done
    ffmpeg -v error -y -f concat -safe 0 -i "$list" -f lavfi -i "color=black:s=400x400:r=$FPS" -filter_complex \
        "[0]fps=$FPS[f];[1][f]overlay=shortest=1,crop=$CROP,scale=222:249:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" \
        "$out"
    rm -f "$list"
}
for dog in ${DOGS:-ozzie}; do
    root=build/frames/rig/$dog
    for anim in walkin walkout awake happy sleepy liedown; do
        [ -d "$root/$anim" ] && gif "build/review/rig_${dog}_$anim.gif" "$root/$anim"
    done
    if [ -d "$root/walkin" ] && [ -d "$root/awake" ] && [ -d "$root/walkout" ]; then
        gif "build/review/rig_${dog}_story.gif" "$root/walkin" "$root/awake" "$root/awake" "$root/walkout"
    fi
    echo "wrote build/review/rig_${dog}_*.gif"
done
