# Command-line builds. The Monkey C extension in Cursor/VS Code does the same
# through "Monkey C: Build for Device" and Run > Start Debugging.
SDK := $(shell cat "$(HOME)/Library/Application Support/Garmin/ConnectIQ/current-sdk.cfg" 2>/dev/null)
DEVICE ?= fr265
KEY ?= $(HOME)/workspace/garmin/keys/developer_key.der
APP := DogFace

.PHONY: build run package art

build:
	"$(SDK)bin/monkeyc" -f monkey.jungle -d $(DEVICE) -y "$(KEY)" -o bin/$(APP).prg -w

run: build
	"$(SDK)bin/connectiq" & sleep 3
	"$(SDK)bin/monkeydo" bin/$(APP).prg $(DEVICE)

package:
	"$(SDK)bin/monkeyc" -f monkey.jungle -e -r -y "$(KEY)" -o bin/$(APP).iq

art:
	uv run tools/make_dog.py
