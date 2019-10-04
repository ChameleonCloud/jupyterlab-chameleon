.PHONY: publish-client
publish-client:
	npm run-script build
	npm publish

.PHONY: watch
watch:
	npm run-script watch
