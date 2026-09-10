# Build/test/lint entry points for humans, editors (nvim :make), and coding
# agents. Delegates to scripts/check.sh, which keeps successful output compact
# and keeps failure output focused on diagnostics.

BUILD_DIR ?= build

.PHONY: all tests lint install symlink clean

all:
	@BUILD_DIR=$(BUILD_DIR) scripts/check.sh build

tests:
	@BUILD_DIR=$(BUILD_DIR) scripts/check.sh test

lint:
	@scripts/check.sh lint

install: all
	meson install -C $(BUILD_DIR)

# hax resolves subagent `hax` invocations through PATH, so development is nicest
# with the dev binary linked there; the symlink tracks every rebuild.
symlink: all
	@mkdir -p "$(HOME)/.local/bin"; \
	target="$$(cd "$(BUILD_DIR)" && pwd)/hax"; \
	link="$(HOME)/.local/bin/hax"; \
	ln -sf "$$target" "$$link" && echo "$$link -> $$target"

clean:
	rm -rf $(BUILD_DIR)

config:
	@if [ ! -f config.h ]; then \
		cp config.def.h config.h && echo "initialized config.h from config.def.h"; \
	else \
		echo "config.h already exists; keeping existing configuration"; \
	fi

check-defaults:
	@python3 scripts/generate_defaults.py . "$$(meson configure $(BUILD_DIR) 2>/dev/null | awk -F: '/personal_defaults/ {gsub(/[[:space:]]/, "", $$2); print $$2}')" /dev/null
