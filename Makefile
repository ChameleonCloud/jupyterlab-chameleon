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
