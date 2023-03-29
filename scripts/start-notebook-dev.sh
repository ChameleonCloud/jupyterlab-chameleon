#!/usr/bin/env bash

if [[ -d /jupyterlab_chameleon ]]; then
	# Remove pip installed version to set up dev
	pip uninstall jupyterlab-chameleon --yes

	# Install dev mode extension
	jupyter labextension develop /jupyterlab_chameleon/
fi
