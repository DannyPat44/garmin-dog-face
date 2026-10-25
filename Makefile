# Command-line builds. The Monkey C extension in Cursor/VS Code does the same
# through "Monkey C: Build for Device" and Run > Start Debugging.
SDK := $(shell cat "$(HOME)/Library/Application Support/Garmin/ConnectIQ/current-sdk.cfg" 2>/dev/null)
JAVA_HOME ?= /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export JAVA_HOME
DEVICE ?= fr265
KEY ?= $(HOME)/workspace/garmin/keys/developer_key.der
APP := DogFace

.PHONY: build run install package art frames preview rig

build:
	"$(SDK)bin/monkeyc" -f monkey.jungle -d $(DEVICE) -y "$(KEY)" -o bin/$(APP).prg -w

run: build
	@pgrep -qf ConnectIQ.app || { "$(SDK)bin/connectiq"; until pgrep -qf ConnectIQ.app; do sleep 1; done; sleep 2; }
	"$(SDK)bin/monkeydo" bin/$(APP).prg $(DEVICE)

# Copy onto a USB-connected watch over MTP (brew install libmtp)
install: build
	@apps=$$(mtp-folders 2>/dev/null | awk '$$2 == "GARMIN" {g=1} g && $$2 == "Apps" {print $$1; exit}'); \
	test -n "$$apps" || { echo "Watch not found: plug it in and close Garmin Express/OpenMTP"; exit 1; }; \
	mtp-sendfile bin/$(APP).prg $$apps > /dev/null && echo "Installed $(APP).prg; unplug the watch"

package:
	"$(SDK)bin/monkeyc" -f monkey.jungle -e -r -y "$(KEY)" -o bin/$(APP).iq

# Rendering every dog and mood takes ~30 minutes; DOGS and MOODS narrow it,
# e.g. make frames DOGS=nova MOODS=happy
frames:
	tools/render_frames.sh

# Watch-size review GIFs of the rendered frames, in build/review/
preview:
	tools/preview_gifs.sh

# Re-encode rendered frames into the watch resources and source/Dogs.mc
art:
	tools/build_art.sh

# Skeleton proof of concept: Ozzie sits down. FUR=1 for the full fur render.
BLENDER ?= /Applications/Blender.app/Contents/MacOS/Blender
rig:
	rm -rf build/frames/rig_poc
	"$(BLENDER)" --background --python tools/blender/rig_poc.py -- --out build/frames/rig_poc \
		$(if $(FUR),--size 400 --samples 40,--no-fur --size 300 --samples 8) > build/render_rig_poc.log
	ffmpeg -v error -y -framerate 10 -i build/frames/rig_poc/%04d.png -f lavfi -i "color=black:s=$(if $(FUR),400x400,300x300):r=10" \
		-filter_complex "[1][0]overlay=shortest=1,split[a][b];[a]palettegen[p];[b][p]paletteuse" build/rig_poc.gif
	@echo "Wrote build/rig_poc.gif"
