# jupyterlab-chameleon

## Client extension

First ensure the tox environment is set up:

```bash
make setup
source .tox/python/bin/activate
```

Then, use the `jlpm` binary provided by the `jupyterlab` Python module to
build and test the extension.

```bash
# 'watch' should automatically recompile .ts files on change and recompile
# the extension for JupyterLab.
jlpm watch
```

To test the extension within JupyterLab, run it in a separate tab:

```bash
jupyter lab --extensions-in-dev-mode
```

## Server extension

First ensure the tox environment is set up:

```bash
make setup
source .tox/python/bin/activate
```

Run `tox` to run unit tests.

```bash
tox
```
