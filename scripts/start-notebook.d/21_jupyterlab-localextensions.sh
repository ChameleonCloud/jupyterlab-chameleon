# Check for local extensions (dev-mode)
if [[ -d /ext ]]; then
  pushd /ext 2>/dev/null

  err_log=jupyter-extension-error.log

  # Install Python extension code
  if [[ -f setup.py ]]; then
    pip list | sponge | grep -q /ext || {
      pip install -e .
      # Hacky way to get the module names
      modules=$(find . -maxdepth 2 -name __init__.py | xargs dirname)
      for mod in $modules; do
        installed=
        for exttype in nbextension serverextension; do
          jupyter "$exttype" enable --py ${mod##./} 2>>$err_log && {
            installed="$exttype"
            break
          }
        done
        if [[ -n "$installed" ]]; then
          echo "Successfully installed $mod as $exttype."
        else
          echo "Failed installing $mod. See $err_log for details."
        fi
      done
    }
  fi

  # Install JS extension code
  if [[ -f package.json ]]; then
    jupyter labextension develop . --overwrite
  fi

  popd 2>/dev/null

  fix-permissions "$CONDA_DIR/share"
fi
