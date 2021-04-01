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
jlpm
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
