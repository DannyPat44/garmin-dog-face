#!/bin/sh
# Watch-size review GIFs of the skeleton renders (tools/render_rig.sh), laid
# out on the round screen as the watch shows them:
#   build/review/rig_<dog>_<anim>.gif  each animation
#   build/review/rig_<dog>_story.gif   walk in, sit for two loops, walk out
set -e
cd "$(dirname "$0")/.."
# The watch crop, in 400px frame units, scaled to whatever size was rendered,
# and where the dog's box sits on the screen (see tools/build_art.sh)
CROP="292*iw/400:328*ih/400:76*iw/400:62*ih/400"
SCREEN=416
DOG_X=97
DOG_Y=134
FPS=10
mkdir -p build/review/.tmp
screen() {  # screen <out> <frame dir>: one animation on the round screen, losslessly
    size=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 "$2/0001.png")
    case $2 in
        */walkin|*/walkout) fit="scale=$SCREEN:$SCREEN:flags=lanczos" at="0:0" ;;
        *) fit="crop=$CROP,scale=222:249:flags=lanczos" at="$DOG_X:$DOG_Y" ;;
    esac
    ffmpeg -v error -y -framerate $FPS -i "$2/%04d.png" -f lavfi -i "color=black:s=${SCREEN}x$SCREEN:r=$FPS" \
        -filter_complex "[0]$fit[d];[1][d]overlay=$at:shortest=1,geq=lum='lum(X,Y)*lte(hypot(X-208,Y-208),208)':cb='128+(cb(X,Y)-128)*lte(hypot(X-208,Y-208),208)':cr='128+(cr(X,Y)-128)*lte(hypot(X-208,Y-208),208)'" \
        -c:v ffv1 "$1"
}
gif() {  # gif <out> <frame dirs...>: the animations, one after another
    out=$1
    shift
    list=build/review/.tmp/list.txt
    : > "$list"
    i=0
    for dir in "$@"; do
        i=$((i + 1))
        screen "build/review/.tmp/$i.mkv" "$dir"
        echo "file '$PWD/build/review/.tmp/$i.mkv'" >> "$list"
    done
    ffmpeg -v error -y -f concat -safe 0 -i "$list" -filter_complex "split[a][b];[a]palettegen[p];[b][p]paletteuse" "$out"
    rm -f build/review/.tmp/*
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
