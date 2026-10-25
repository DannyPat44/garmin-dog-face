#!/bin/sh
# Review GIFs from rendered frames (tools/render_frames.sh), cropped and scaled
# exactly as on the watch: build/review/<dog>_<mood>.gif plus all.gif, a grid
# with one row per dog and one column per mood.
set -e
cd "$(dirname "$0")/.."
CROP=292:328:76:62
WIDTH=222
HEIGHT=249
FPS=10
DOGS=${DOGS:-puppy nova ozzie}
MOODS=${MOODS:-awake happy sleepy}
mkdir -p build/review
inputs=""
n=0
for dog in $DOGS; do
    for mood in $MOODS; do
        ffmpeg -v error -y -framerate $FPS -i "build/frames/$dog/$mood/%04d.png" \
            -f lavfi -i "color=black:s=400x400:r=$FPS" -filter_complex \
            "[1][0]overlay=shortest=1,crop=$CROP,scale=$WIDTH:$HEIGHT:flags=lanczos,split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a" \
            "build/review/${dog}_$mood.gif"
        inputs="$inputs -i build/review/${dog}_$mood.gif"
        n=$((n + 1))
    done
done
cols=$(echo $MOODS | wc -w | tr -d ' ')
layout=""
i=0
while [ $i -lt $n ]; do
    layout="$layout|$((i % cols * WIDTH))_$((i / cols * HEIGHT))"
    i=$((i + 1))
done
ffmpeg -v error -y $inputs -filter_complex \
    "xstack=inputs=$n:layout=${layout#|}:fill=black,split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a" \
    build/review/all.gif
echo "wrote build/review/all.gif and $n per-dog GIFs"
