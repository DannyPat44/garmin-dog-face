#!/bin/sh
# Turn the skeleton renders (tools/render_rig.sh) into watch resources for every
# dog, at each screen size in SCREENS (the FR265's 416px and the FR255's
# 260px). Connect IQ picks resources-round-<size>x<size> by the watch's screen:
#   resources-round-<size>x<size>/animations/<dog>_<clip>/  Monkey Motion
#       animation, encoded for that watch's display
#   resources-round-<size>x<size>/drawables/<dog>_<mood>.png  first frame of
#       each mood loop, drawn under the clips (see Story.endStill)
#   and their animations.xml and drawables.xml
#   source/Dogs.mc  the list of dogs and their resources, for the watch face
# Clips, in Story's order: the mood loops (awake happy sleepy), walk in, walk
# out, lie down, and get up (lie down played backwards). The walks fill the
# whole round screen (render_rig frames them that way); the rest are cropped
# to the dog's box (DogLayout.box). The launcher icon and the clock fonts
# (tools/make_font.py) are left as they are.
# DOGS lists the dogs, e.g. DOGS="ozzie" for a face with only Ozzie; FRAMES
# is where the renders are (default build/frames/rig).
set -e
cd "$(dirname "$0")/.."
SDK=$(cat "$HOME/Library/Application Support/Garmin/ConnectIQ/current-sdk.cfg")
export JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}
export PATH="$JAVA_HOME/bin:$PATH"
# Crop to the dog (and its Zzz) before scaling to the watch size; in 400px
# frame units, scaled to whatever size was rendered
CROP="292*iw/400:328*ih/400:76*iw/400:62*ih/400"
# The screen size and the device whose display each size is encoded for
SCREENS=${SCREENS:-"416:fr265 260:fr255"}
FPS=10
DOGS=${DOGS:-"millie nova ozzie"}
FRAMES=${FRAMES:-build/frames/rig}
CLIPS="awake happy sleepy walkin walkout liedown getup"
MOODS="awake happy sleepy"

capitalise() { echo "$1" | awk '{print toupper(substr($0,1,1)) substr($0,2)}'; }
# scaled <px> <screen>: a size on the 416px screen, scaled to <screen> (as DogLayout does)
scaled() { awk "BEGIN { printf \"%d\", $1 * $2 / 416 + 0.5 }"; }

for spec in $SCREENS; do
    screen=${spec%%:*}
    device=${spec#*:}
    out="resources-round-${screen}x$screen"
    width=$(scaled 222 "$screen")
    height=$(scaled 249 "$screen")
    # Walking dogs fade in and out over this many pixels at the sides of the box
    fade=$(scaled 18 "$screen")
    mkdir -p "build/art/$screen"
    # The edge fade: white, ramping to black over the fade at the left and right
    ffmpeg -v error -y -f lavfi -i "color=white:s=${width}x$height" -vf \
        "geq=lum='255*min(1,min(X,W-1-X)/$fade)':cb=128:cr=128" -frames:v 1 "build/art/edge_fade_$screen.png"
    # The round screen, for the walks: white inside, black outside
    ffmpeg -v error -y -f lavfi -i "color=white:s=${screen}x$screen" -vf \
        "geq=lum='255*clip(($screen/2-hypot(X-$screen/2+0.5,Y-$screen/2+0.5))+0.5,0,1)':cb=128:cr=128" \
        -frames:v 1 "build/art/screen_mask_$screen.png"

    rm -rf "$out/animations" "$out/drawables"
    mkdir -p "$out/animations" "$out/drawables"
    animations_xml="<animations>"
    drawables_xml="<drawables>
    <!-- First frame of each mood loop, drawn under the clips -->"
    for dog in $DOGS; do
        for clip in $CLIPS; do
            name="${dog}_$clip"
            id="$(capitalise "$dog")$(capitalise "$clip")"
            src=$clip
            reverse=""
            if [ "$clip" = getup ]; then
                src=liedown
                reverse="reverse,"
            fi
            frames="$FRAMES/$dog/$src/%04d.png"
            size=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 "$FRAMES/$dog/$src/0001.png")
            # Walks: the whole screen, masked to its circle. The rest: cropped
            # to the box, with its edges faded
            if [ "$clip" = walkin ] || [ "$clip" = walkout ]; then
                fit="scale=$screen:$screen:flags=lanczos"
                mask="build/art/screen_mask_$screen.png"
                res=${screen}x$screen
            else
                fit="crop=$CROP,scale=$width:$height:flags=lanczos"
                mask="build/art/edge_fade_$screen.png"
                res=${width}x$height
            fi
            # Flatten onto black (the watch background), mask and quantise to
            # a GIF for Monkey Motion, with a palette per frame: one palette
            # for a whole walk is mostly black screen, and greys out her fur
            # monkeym names its output after the GIF
            gif="build/art/$screen/$name.gif"
            ffmpeg -v error -y -framerate $FPS -i "$frames" -f lavfi -i "color=black:s=${size}x$size:r=$FPS" \
                -loop 1 -i "$mask" -filter_complex \
                "[1][0]overlay=shortest=1,${reverse}$fit,format=rgb24[d];[2]format=rgb24[m];[d][m]blend=all_mode=multiply:shortest=1,split[a][b];[a]palettegen=stats_mode=single[p];[b][p]paletteuse=new=1:dither=sierra2_4a" \
                "$gif"
            bash "${SDK}bin/monkeym" -v "$gif" -d "$device" -r "$res" -f $FPS \
                -o "$out/animations/$name" > "build/art/$screen/monkeym_$name.log"
            # monkeym records the absolute source path; keep the repo free of local paths
            sed -i '' "s|# Video file: .*/build/|# Video file: build/|" "$out/animations/$name/$name.mmm"
            animations_xml="$animations_xml
    <animation id=\"${id}Animation\" filename=\"$name/$name.mmm\" />"
            echo "built $name at ${screen}px"
        done
        for mood in $MOODS; do
            name="${dog}_$mood"
            id="$(capitalise "$dog")$(capitalise "$mood")"
            ffmpeg -v error -y -i "$FRAMES/$dog/$mood/0001.png" -vf "crop=$CROP,scale=$width:$height:flags=lanczos" \
                "$out/drawables/$name.png"
            drawables_xml="$drawables_xml
    <bitmap id=\"$id\" filename=\"$name.png\" />"
        done
    done
    printf '%s\n</animations>\n' "$animations_xml" > "$out/animations/animations.xml"
    printf '%s\n</drawables>\n' "$drawables_xml" > "$out/drawables/drawables.xml"
done

# The same resource ids at every size
stills_mc=""
clips_mc=""
names_mc=""
for dog in $DOGS; do
    names_mc="$names_mc \"$(capitalise "$dog")\","
    stills_mc="$stills_mc
        ["
    clips_mc="$clips_mc
        ["
    for clip in $CLIPS; do
        clips_mc="$clips_mc Rez.Drawables.$(capitalise "$dog")$(capitalise "$clip")Animation,"
    done
    for mood in $MOODS; do
        stills_mc="$stills_mc Rez.Drawables.$(capitalise "$dog")$(capitalise "$mood"),"
    done
    stills_mc="$stills_mc ],"
    clips_mc="$clips_mc ],"
done
cat > source/Dogs.mc <<MC
// Generated by tools/build_art.sh from its DOGS list; don't edit by hand.
import Toybox.Lang;
import Toybox.WatchUi;

// The dogs' names, for the settings
function dogNames() as Array<String> {
    return [$names_mc ];
}

// [dog][mood], moods in the order $MOODS
function dogStills() as Array<Array<ResourceId> > {
    return [$stills_mc
    ];
}

// [dog][clip], clips in the order $CLIPS (Story's constants)
function dogClips() as Array<Array<ResourceId> > {
    return [$clips_mc
    ];
}
MC
