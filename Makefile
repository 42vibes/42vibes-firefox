PYTHON ?= python3
PYTHONPATH ?=

.PHONY: build validate package check

build:
	$(PYTHON) build.py

validate:
	$(PYTHON) validate.py

package: build
	@mkdir -p dist
	@rm -f dist/42vibes-firefox-dark.zip dist/42vibes-firefox-light.zip
	cd firefox/42vibes-dark && zip -qr ../../dist/42vibes-firefox-dark.zip . -x '*.DS_Store'
	cd firefox/42vibes-light && zip -qr ../../dist/42vibes-firefox-light.zip . -x '*.DS_Store'
	@echo "package: dist/42vibes-firefox-dark.zip dist/42vibes-firefox-light.zip"

check: build validate
