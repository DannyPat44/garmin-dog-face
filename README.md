# Dog Face

A Connect IQ watch face for Garmin Forerunners with a cartoon dog in the middle,
inspired by the "Cuddly Cat" face. The dog's mood follows your day:

| Mood   | When                                 |
|--------|--------------------------------------|
| sleepy | 10pm to 6am                          |
| happy  | step goal reached                    |
| awake  | the rest of the time                 |

Date and time sit above the dog; heart rate, steps and battery below. On AMOLED
watches (FR265/965/970) the always-on mode shows only a dim, shifting clock to
stay within Garmin's burn-in rules.

## Layout

- `source/DogFaceView.mc`: drawing and mood logic
- `resources/drawables/`: dog artwork (generated) and launcher icon
- `tools/make_dog.py`: draws the dog. Edit colors/shapes, then `make art`
- `manifest.xml`: app id and the Forerunner models it builds for

## Build and run

Needs the Connect IQ SDK and device files from the SDK Manager, plus Java 17
(`JAVA_HOME` is set in `~/.zprofile`).

```sh
make run DEVICE=fr265   # build and open in the simulator
make build DEVICE=fr965 # just build bin/DogFace.prg
make package            # store-ready bin/DogFace.iq for every device
```

In Cursor/VS Code, open this folder and press F5 to pick a device and launch the simulator.

## Sideload onto the watch

1. `make build DEVICE=<your model>`
2. Connect the watch by USB. macOS needs an MTP client such as [OpenMTP](https://openmtp.ganeshrvel.com/).
3. Copy `bin/DogFace.prg` into `GARMIN/APPS/` on the watch, then unplug it.
4. Pick "Dog Face" from the watch face list.
