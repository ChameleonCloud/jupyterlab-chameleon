.PHONY: setup
setup:
	tox --notest

.PHONY: publish-client
publish-client:
	npm run-script build
	npm publish

.PHONY: publish-server
publish-server:
	@ rm -rf build/ dist/
	python setup.py sdist bdist_wheel
	twine upload dist/*

.PHONY: watch
watch:
	jlpm watch:src
