# Doggos

A Connect IQ watch face for the Garmin Forerunner 265 where three fluffy,
animated 3D dogs take turns on your wrist. Every dog is modelled in code and
rendered with Blender, so you can make your own.

| Millie | Nova | Ozzie | Nova, asleep |
|---|---|---|---|
| ![Millie](store/screenshot_millie.png) | ![Nova](store/screenshot_nova.png) | ![Ozzie](store/screenshot_ozzie.png) | ![Nova asleep](store/screenshot_nova_sleepy.png) |

- **Millie**: a tri-colour hound pup with a red MI11IE collar.
- **Nova**: a golden long-haired dachshund in a straw sombrero with a rainbow band.
- **Ozzie**: a red cattle dog mix with one pricked ear and her tennis ball.

A different dog comes on each hour, picked at random. Dogs only swap while the
screen is off, so you never see the change. Each dog has three moods:

| Mood   | When                 | Animation                                        |
|--------|----------------------|--------------------------------------------------|
| sleepy | 10pm to 6am          | lying down, deep breaths, ear twitches, Zzz      |
| happy  | step goal reached    | tongue out, bouncing, fast tail wag              |
| awake  | the rest of the time | head tilt, blink, tail wag                       |

The animation loops while the screen is fully on; otherwise its first frame
shows as a still. The battery (with percentage) and date sit at the top, then
a chunky Fredoka clock, steps on the left and heart rate on the right. The
clock and stats are drawn on a layer above the dog, so the dog never shows
without the rest of the face. In always-on mode the AMOLED screen shows only a
dim, shifting clock to stay within Garmin's burn-in rules.

## Setup

macOS with Homebrew:

```sh
brew install --cask blender     # Blender 5.x renders the dogs
brew install ffmpeg libmtp openjdk@17
```

- **Connect IQ SDK**: install the SDK Manager from
  https://developer.garmin.com/connect-iq/sdk/, then download the latest SDK
  and the Forerunner 265 device files (needs a Garmin login).
- **Java 17**: `export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home`
  in your shell profile.
- **Developer key**: every Connect IQ app is signed. Make one once and keep it
  out of the repo:

  ```sh
  openssl genrsa -out developer_key.pem 4096
  openssl pkcs8 -topk8 -inform PEM -outform DER -in developer_key.pem -out developer_key.der -nocrypt
  ```

  The Makefile looks for `~/workspace/garmin/keys/developer_key.der`; pass
  `KEY=/path/to/developer_key.der` to use another location. Keep the key: store
  updates must be signed with the same one.

## Commands

| Command | What it does |
|---|---|
| `make run` | Build and open in the simulator |
| `make install` | Build and copy onto a USB-connected watch (close Garmin Express first) |
| `make package` | Build `bin/Doggos.iq` for the Connect IQ Store |
| `make frames` | Render every dog's moods with Blender into `build/frames/` (~30 min; `DOGS=nova MOODS=happy` narrows it) |
| `make preview` | Watch-size review GIFs in `build/review/`, plus a grid of all of them |
| `make art` | Encode rendered frames into the watch resources and `source/Dogs.mc` |
| `make rig` | Skeleton proof of concept: Ozzie sits down (`FUR=1` for fur, ~10 min) |

Quick single-frame preview while you tweak a dog (`--no-fur` takes seconds):

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python tools/blender/dog.py -- \
    --dog nova --mood awake --still build/preview.png [--no-fur]
```

## How the dogs are made

Following [Simon Willison's approach](https://til.simonwillison.net/llms/blender-coding-agents-macos),
everything is built in code in `tools/blender/dog.py`:

1. Each dog is sculpted from blended metaball ellipsoids (body, head, ears,
   tail), converted to a smooth mesh, and covered in particle fur with the
   Principled Hair BSDF.
2. Markings are procedural: coloured ellipsoid patches with noisy edges, so
   the same coat paints the skin and the fur.
3. Props are built in code too: Nova's straw sombrero, Ozzie's tennis ball and
   Millie's collar lettering (Fredoka, from `tools/fonts/`).
4. Each mood keys a 30-frame loop (3 seconds at 10 fps) and renders with
   Cycles on a transparent background.
5. `tools/build_art.sh` crops and flattens the frames onto black, encodes them
   with Garmin's Monkey Motion (`monkeym`), and writes the resource XML and
   `source/Dogs.mc`, the list of dogs the watch face rotates through.

Animations stream from the app's resources rather than memory: the face uses
about 12 KB of its 128 KB memory limit, and nine animations make a 6.7 MB app
(the FR265 allows 64 MB).

### Make your own dog

1. In `tools/blender/dog.py`, write a `build_<name>(pose)` function (copy
   `build_nova` or `build_ozzie` as a starting point), with `sitting` and
   `lying` poses, and add it to `DOGS` and the `--dog` choices.
2. Iterate with `--still` and `--no-fur` until you like the shape, then
   render: `make frames DOGS=<name>`.
3. Add `<name>:<name>` to `DOGS` in `tools/build_art.sh` (or pass it as
   `DOGS="<name>:<name>" make art` for a face with only your dog).
4. `make run` to see it in the simulator, `make install` to put it on your watch.

To publish your own version, change the app `id` in `manifest.xml` and the
name in `resources/strings/strings.xml`.

## Work in progress: skeletons

The dogs currently swap while the screen is off. The goal is for each dog to
walk in at the top of the hour and sit down. A cross-fade between the
standing and sitting sculpts looked wrong, so `tools/blender/rig_poc.py` tries
a skeleton instead: Ozzie's body and legs become one mesh bound to an 11-bone
armature with Blender's automatic weights, and sitting is just bone rotations
(the spine swings around the shoulders, the back legs fold, the head stays
level). The fur rides on the deformed mesh. Run `make rig` to see it.

## Layout

- `source/DogFaceView.mc`: layout, rotation, mood logic, animation playback
- `source/Dogs.mc`: the dog list (generated by `build_art.sh`)
- `resources/animations/`, `resources/drawables/`: Monkey Motion animations
  and still frames (generated)
- `tools/blender/dog.py`: the dogs, props, scene and animations
- `tools/blender/rig_poc.py`: the skeleton proof of concept
- `tools/render_frames.sh`, `tools/build_art.sh`, `tools/preview_gifs.sh`: the art pipeline
- `tools/make_font.py`: turns `tools/fonts/Fredoka.ttf` (SIL OFL) into the clock's bitmap font
- `store/`: Connect IQ Store listing and screenshots
