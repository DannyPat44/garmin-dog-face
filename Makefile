# Command-line builds. The Monkey C extension in Cursor/VS Code does the same
# through "Monkey C: Build for Device" and Run > Start Debugging.
SDK := $(shell cat "$(HOME)/Library/Application Support/Garmin/ConnectIQ/current-sdk.cfg" 2>/dev/null)
JAVA_HOME ?= /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export JAVA_HOME
DEVICE ?= fr265
KEY ?= $(HOME)/workspace/garmin/keys/developer_key.der
APP := Doggos

.PHONY: build run install package art frames preview rig rig-preview

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

# Dogs on the shared skeleton (tools/blender/dog_rig.py): DOGS and ANIMS narrow it
rig:
	tools/render_rig.sh

# Watch-size GIFs of the skeleton renders, including a walk-in/sit/walk-out story
rig-preview:
	tools/preview_rig.sh
