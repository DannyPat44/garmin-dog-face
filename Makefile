# Command-line builds. The Monkey C extension in Cursor/VS Code does the same
# through "Monkey C: Build for Device" and Run > Start Debugging.
SDK := $(shell cat "$(HOME)/Library/Application Support/Garmin/ConnectIQ/current-sdk.cfg" 2>/dev/null)
JAVA_HOME ?= /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export JAVA_HOME
DEVICE ?= fr265
KEY ?= $(HOME)/workspace/garmin/keys/developer_key.der
APP := DogFace

.PHONY: build run install package art

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

# Rendering takes ~12 minutes; build_art alone re-encodes existing frames
art:
	tools/render_frames.sh
	tools/build_art.sh
