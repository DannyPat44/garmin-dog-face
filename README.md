# Dog Face

A Connect IQ watch face for the Garmin Forerunner 265 with an animated, plush
3D puppy, inspired by the "Cuddly Cat" face. The puppy is modelled on a real
tri-colour hound pup: black saddle, tan face and legs, white blaze, chest and
paws, tan eyebrow dots and floppy ears.

| Mood   | When               | Animation                              |
|--------|--------------------|----------------------------------------|
| sleepy | 10pm to 6am        | lying on its paws, slow breathing, Zzz |
| happy  | step goal reached  | tongue out, bouncing, fast tail wag    |
| awake  | the rest of the time | head tilt, blink, tail wag           |

The animation plays twice whenever you raise your wrist; otherwise the first
frame shows as a still. Battery sits at the top, then the time, steps (left),
heart rate (right) and the date. In always-on mode the AMOLED screen shows only
a dim, shifting clock to stay within Garmin's burn-in rules.

## How the art is made

Following [Simon Willison's approach](https://til.simonwillison.net/llms/blender-coding-agents-macos),
the puppy is built entirely in code and rendered with Blender:

1. `tools/blender/dog.py` builds the model (furry ellipsoids with painted
   markings), the ground and lights, keys a 30-frame looping animation for a
   mood and renders it with Cycles.
2. `tools/render_frames.sh` renders all three moods into `build/frames/` (~30 min).
3. `tools/build_art.sh` flattens frames onto black, encodes them with Garmin's
   Monkey Motion into `resources/animations/`, and saves the still frames and
   launcher icon into `resources/drawables/`.

`make art` runs both steps. To tweak the dog, edit the colours, shapes or poses
in `dog.py` and preview a single frame quickly:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python tools/blender/dog.py -- \
    --mood awake --still build/preview.png            # add --no-fur for a 10 second draft
```

Needs Blender (`brew install --cask blender`) and ffmpeg (`brew install ffmpeg`).

## Layout

- `source/DogFaceView.mc`: layout, mood logic, animation playback
- `resources/animations/`: Monkey Motion animations (generated)
- `resources/drawables/`: still frames and launcher icon (generated)
- `tools/`: the Blender model and art build scripts
- `manifest.xml`: app id and target device

## Build and run

Needs the Connect IQ SDK and device files from the SDK Manager, plus Java 17
(`JAVA_HOME` is set in `~/.zprofile`).

```sh
make run                # build and open in the simulator
make build              # just build bin/DogFace.prg
make package            # store-ready bin/DogFace.iq
```


## Sideload onto the watch

1. `make build`
2. Connect the watch by USB. macOS needs an MTP client such as [OpenMTP](https://openmtp.ganeshrvel.com/).
3. Copy `bin/DogFace.prg` into `GARMIN/APPS/` on the watch, then unplug it.
4. Pick "Dog Face" from the watch face list.
