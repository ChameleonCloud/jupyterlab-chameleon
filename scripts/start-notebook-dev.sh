#!/usr/bin/env bash

export GRANT_SUDO=yes
export CHOWN_EXTRA=/work
export CHOWN_EXTRA_ARGS=-R
export JUPYTER_ENABLE_LAB=yes

if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

start-notebook.sh \
  --ServerApp.password_required=False \
  --autoreload \
  "$@"
