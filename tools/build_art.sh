#!/bin/sh
# Turn rendered frames (tools/render_frames.sh) into watch resources for every dog:
#   resources/animations/<dog>_<mood>/  Monkey Motion animation for the FR265
#   resources/drawables/<dog>_<mood>.png  first frame, shown while the animation is idle
#   resources/animations/animations.xml, resources/drawables/drawables.xml
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
# Render name:watch name (Millie was rendered as "puppy")
DOGS="puppy:millie nova:nova ozzie:ozzie"
MOODS="awake happy sleepy"

capitalise() { echo "$1" | awk '{print toupper(substr($0,1,1)) substr($0,2)}'; }

rm -rf resources/animations/dog_* resources/drawables/dog_*.png
animations_xml="<animations>"
drawables_xml="<drawables>
    <bitmap id=\"LauncherIcon\" filename=\"launcher_icon.png\" />
    <!-- First frame of each animation, drawn while the animation is idle -->"
for pair in $DOGS; do
    src=${pair%%:*}
    dog=${pair#*:}
    for mood in $MOODS; do
        name="${dog}_$mood"
        id="$(capitalise "$dog")$(capitalise "$mood")"
        frames="build/frames/$src/$mood/%04d.png"
        # Flatten onto black (the watch background) and quantise to a GIF for Monkey Motion
        ffmpeg -v error -y -framerate $FPS -i "$frames" -f lavfi -i "color=black:s=400x400:r=$FPS" -filter_complex \
            "[1][0]overlay=shortest=1,crop=$CROP,scale=$WIDTH:$HEIGHT:flags=lanczos,split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a" \
            "build/$name.gif"
        rm -rf "resources/animations/$name"
        bash "${SDK}bin/monkeym" -v "build/$name.gif" -d fr265 -r ${WIDTH}x${HEIGHT} -f $FPS \
            -o "resources/animations/$name" > "build/monkeym_$name.log"
        ffmpeg -v error -y -i "build/frames/$src/$mood/0001.png" -vf "crop=$CROP,scale=$WIDTH:$HEIGHT:flags=lanczos" \
            "resources/drawables/$name.png"
        animations_xml="$animations_xml
    <animation id=\"${id}Animation\" filename=\"$name/$name.mmm\" />"
        drawables_xml="$drawables_xml
    <bitmap id=\"$id\" filename=\"$name.png\" />"
        echo "built $name"
    done
done
printf '%s\n</animations>\n' "$animations_xml" > resources/animations/animations.xml
printf '%s\n</drawables>\n' "$drawables_xml" > resources/drawables/drawables.xml

ffmpeg -v error -y -f lavfi -i "color=black:s=400x400" -i build/frames/puppy/happy/0001.png -filter_complex \
    "[0][1]overlay,crop=240:240:80:50,scale=60:60:flags=lanczos" -frames:v 1 resources/drawables/launcher_icon.png
