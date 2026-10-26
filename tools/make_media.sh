#!/bin/sh
# The README's GIFs and videos and the store's screenshots, from the skeleton
# renders (tools/render_rig.sh) laid out on the watch face as the FR265 shows
# them: the dog layer (loops in the dog's box, walks across the whole round
# screen) under the face's clock and stats (docs/media/face_ui.png, from a
# simulator capture by tools/face_ui.py).
#   docs/media/<dog>_hour.gif, .mp4   walk in, sit, walk out
#   docs/media/bedtime.gif, .mp4      Millie lying down for the night
#   docs/media/happy.gif, .mp4        Ozzie with her step goal met
#   store/screenshot_<dog>[_happy|_sleepy].png, store/cover.png, store/hero.png
set -e
cd "$(dirname "$0")/.."
CROP="292*iw/400:328*ih/400:76*iw/400:62*ih/400"
SCREEN=416
FPS=10
GIF=280
UI=docs/media/face_ui.png
FRAMES=build/frames/rig
TMP=build/media/tmp
mkdir -p "$TMP" docs/media store
# The round screen: white inside, black outside
ffmpeg -v error -y -f lavfi -i "color=white:s=${SCREEN}x$SCREEN" -vf \
    "geq=lum='255*clip(($SCREEN/2-hypot(X-$SCREEN/2+0.5,Y-$SCREEN/2+0.5))+0.5,0,1)':cb=128:cr=128" \
    -frames:v 1 "$TMP/circle.png"

# clip <out.mkv> <frame dir>: one animation on the watch face, losslessly
clip() {
    size=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 "$2/0001.png")
    case $2 in
        */walkin|*/walkout) fit="scale=$SCREEN:$SCREEN:flags=lanczos" at="0:0" ;;
        *) fit="crop=$CROP,scale=222:249:flags=lanczos" at="97:134" ;;
    esac
    # The face's text is white on black, so it goes over the dog with "lighten"
    ffmpeg -v error -y -framerate $FPS -i "$2/%04d.png" -f lavfi -i "color=black:s=${SCREEN}x$SCREEN:r=$FPS" \
        -loop 1 -i "$TMP/circle.png" -loop 1 -i "$UI" -filter_complex \
        "[0]$fit[d];[1][d]overlay=$at:shortest=1,format=rgb24[s];[2]format=rgb24[m];[s][m]blend=all_mode=multiply:shortest=1[r];[3]format=rgb24[u];[r][u]blend=all_mode=lighten:shortest=1" \
        -c:v ffv1 "$1"
}

# movie <name> <frame dirs...>: docs/media/<name>.gif and .mp4 of the clips in turn
movie() {
    name=$1
    shift
    list="$TMP/list.txt"
    : > "$list"
    i=0
    for dir in "$@"; do
        i=$((i + 1))
        clip "$TMP/$name-$i.mkv" "$dir"
        echo "file '$PWD/$TMP/$name-$i.mkv'" >> "$list"
    done
    # A palette per frame, so fur keeps its colour against all that black
    ffmpeg -v error -y -f concat -safe 0 -i "$list" -filter_complex \
        "scale=$GIF:$GIF:flags=lanczos,split[a][b];[a]palettegen=stats_mode=single[p];[b][p]paletteuse=new=1:dither=sierra2_4a" \
        "docs/media/$name.gif"
    ffmpeg -v error -y -f concat -safe 0 -i "$list" -c:v libx264 -pix_fmt yuv420p -crf 20 -r 30 \
        -movflags +faststart "docs/media/$name.mp4"
    echo "made docs/media/$name.gif and .mp4"
}

# still <out.png> <frame png> [width]: one frame on the watch face, as a small PNG
still() {
    size=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 "$2")
    ffmpeg -v error -y -i "$2" -f lavfi -i "color=black:s=${SCREEN}x$SCREEN:d=1:r=1" -i "$TMP/circle.png" -i "$UI" \
        -filter_complex "[0]crop=$CROP,scale=222:249:flags=lanczos[d];[1][d]overlay=97:134,format=rgb24[s];[2]format=rgb24[m];[s][m]blend=all_mode=multiply[r];[3]format=rgb24[u];[r][u]blend=all_mode=lighten,scale=${3:-$SCREEN}:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" \
        -frames:v 1 "$1"
}

for dog in millie nova ozzie; do
    r=$FRAMES/$dog
    movie "${dog}_hour" "$r/walkin" "$r/awake" "$r/walkout"
    still "store/screenshot_$dog.png" "$r/awake/0001.png"
    still "store/screenshot_${dog}_happy.png" "$r/happy/0012.png"
    still "store/screenshot_${dog}_sleepy.png" "$r/sleepy/0001.png"
done
movie bedtime "$FRAMES/millie/liedown" "$FRAMES/millie/sleepy"
movie happy "$FRAMES/ozzie/happy" "$FRAMES/ozzie/happy"

# Store art: the three dogs side by side (hero), and Ozzie alone (cover)
still "$TMP/m.png" "$FRAMES/millie/awake/0001.png"
still "$TMP/n.png" "$FRAMES/nova/awake/0001.png"
still "$TMP/o.png" "$FRAMES/ozzie/awake/0001.png"
ffmpeg -v error -y -f lavfi -i "color=black:s=1440x720:d=1:r=1" -i "$TMP/m.png" -i "$TMP/n.png" -i "$TMP/o.png" -filter_complex \
    "[1]scale=440:440[a];[2]scale=440:440[b];[3]scale=440:440[c];[0][a]overlay=40:140[x];[x][b]overlay=500:140[y];[y][c]overlay=960:140" \
    -frames:v 1 store/hero.png
ffmpeg -v error -y -f lavfi -i "color=black:s=500x500:d=1:r=1" -i "$TMP/o.png" -filter_complex \
    "[1]scale=480:480[a];[0][a]overlay=10:10,split[s][t];[s]palettegen[p];[t][p]paletteuse" -frames:v 1 store/cover.png
echo "made store/ screenshots, hero and cover"
