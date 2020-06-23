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
	npm run-script watch
