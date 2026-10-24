#!/bin/sh
# Turn rendered frames (tools/render_frames.sh) into watch resources:
#   resources/animations/dog_<mood>/  Monkey Motion animation for the FR265
#   resources/drawables/dog_<mood>.png  first frame, shown while the animation is idle
#   resources/drawables/launcher_icon.png
set -e
cd "$(dirname "$0")/.."
SDK=$(cat "$HOME/Library/Application Support/Garmin/ConnectIQ/current-sdk.cfg")
export JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}
export PATH="$JAVA_HOME/bin:$PATH"
# Frames are 400x400; crop to the dog (and its Zzz) before scaling to the watch size
CROP=292:328:76:62
WIDTH=222
HEIGHT=249
FPS=10

for mood in awake happy sleepy; do
    frames="build/frames/$mood/%04d.png"
    # Flatten onto black (the watch background) and quantise to a GIF for Monkey Motion
    ffmpeg -v error -y -framerate $FPS -i "$frames" -f lavfi -i "color=black:s=400x400" -filter_complex \
        "[1][0]overlay=shortest=1,crop=$CROP,scale=$WIDTH:$HEIGHT:flags=lanczos,split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a" \
        "build/$mood.gif"
    rm -rf "resources/animations/dog_$mood"
    bash "${SDK}bin/monkeym" -v "build/$mood.gif" -d fr265 -r ${WIDTH}x${HEIGHT} -f $FPS \
        -o "resources/animations/dog_$mood" > "build/monkeym_$mood.log"
    ffmpeg -v error -y -i "build/frames/$mood/0001.png" -vf "crop=$CROP,scale=$WIDTH:$HEIGHT:flags=lanczos" \
        "resources/drawables/dog_$mood.png"
    echo "built $mood"
done

ffmpeg -v error -y -f lavfi -i "color=black:s=400x400" -i build/frames/happy/0001.png -filter_complex \
    "[0][1]overlay,crop=240:240:80:50,scale=60:60:flags=lanczos" -frames:v 1 resources/drawables/launcher_icon.png
