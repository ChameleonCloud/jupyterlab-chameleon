DOCKER_REGISTRY = docker.chameleoncloud.org
IMAGE_NAME = jupyterhub-user
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
	python -m build
	twine upload dist/*

.PHONY: watch
watch:
	jlpm watch

.PHONY: notebook-build
notebook-build:
	docker build -t docker.chameleoncloud.org/jupyterhub-user:dev .

.PHONY: hub-build-release
notebook-build-release:
	docker build --platform $(RELEASE_PLATFORM) -t $(DOCKER_REGISTRY)/$(IMAGE_NAME):$(TAG_VERSION) --target $(RELEASE_TARGET) .

.PHONY: notebook-publish
notebook-publish:
	docker build --no-cache --platform linux/amd64 -t docker.chameleoncloud.org/jupyterhub-user:dev .
	docker push docker.chameleoncloud.org/jupyterhub-user:dev
