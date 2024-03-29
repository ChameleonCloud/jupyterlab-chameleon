DOCKER_REGISTRY = ghcr.io/chameleoncloud
IMAGE_NAME = jupyterlab-chameleon
DEV_TARGET = dev
RELEASE_TARGET = release
RELEASE_PLATFORM = linux/amd64
TAG_VERSION = $(shell git log -n1 --format=%h -- .)

.PHONY: setup
setup:
	@echo "NOTE: this will take a while because we have to build the client "
	@echo "component of the extension. Expect this to take ~5 minutes."
	tox --notest

.PHONY: publish
publish:
	@ rm -rf build/ dist/
	python3 -m build
	twine upload -u chameleoncloud dist/*

.PHONY: watch
watch:
	jlpm watch

.PHONY: notebook-build
notebook-build:
	docker build -t ghcr.io/chameleoncloud/jupyterlab-chameleon:dev .

.PHONY: hub-build-release
notebook-build-release:
	docker build --platform $(RELEASE_PLATFORM) -t $(DOCKER_REGISTRY)/$(IMAGE_NAME):$(TAG_VERSION) --target $(RELEASE_TARGET) .

.PHONY: notebook-publish
notebook-publish:
	docker build --no-cache --platform linux/amd64 -t ghcr.io/chameleoncloud/jupyterlab-chameleon:dev .
	docker push ghcr.io/chameleoncloud/jupyterlab-chameleon:dev
