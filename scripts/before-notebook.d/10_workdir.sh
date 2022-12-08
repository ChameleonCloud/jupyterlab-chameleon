set -x

workdir=/work
expdir=/exp
archivedir=/tmp/_archive

if [[ ! -d "$workdir" ]]; then
  mkdir -p "$workdir"
fi

# Remove artifacts from mounting remote volume
rm -rf "$workdir/lost+found"

# Set up Git author config
git config --global user.name "$NB_USER"
git config --global user.email "$NB_USER@jupyter.chameleoncloud.org"

git_fetch_latest() {
  local repo="$1"
  # Gracefully fail
  (cd "$repo" && git stash && git pull && git stash pop) || {
    echo "Failed to pull latest changes from remote"
  }
}

git_fetch() {
  local remote="$1"
  local checkout="$2"

  if [[ ! -d "$checkout/.git" ]]; then
    # Splits the remote into remote@ref. Note we must always ensure to include
    # an @ here, or the checkout will fail
    remote_url=${remote%@*}
    reference=${remote#*@}
    git clone "$remote_url" $archivedir
    pushd $archivedir
    mkdir -p $checkout
    git archive --format=tar "$reference" | tar xf - -C "$checkout"
    popd
    rm -rf $archivedir
  else
    git_fetch_latest $checkout
  fi
}

setup_default_server() {
  # Copy examples and other "first launch" files over.
  rsync -aq /etc/jupyter/serverroot/ $workdir/
}

setup_experiment_server() {
  if [[ "${ARTIFACT_CONTENTS_PROTO:-}" == "http" ]]; then
    echo "Downloading via wget"
    mkdir -p $archivedir
    wget -P $archivedir "$ARTIFACT_CONTENTS_URL"
    archivefile="$archivedir/$(find $archivedir -type f -exec basename {} \; | head -n1)"
  elif [[ "${ARTIFACT_CONTENTS_PROTO:-}" == "git" ]]; then
    echo "Fetching with git"
    git_fetch "$ARTIFACT_CONTENTS_URL" $workdir
  fi
  # Contents URL may contain sensitive information (e.g. creds that are
  # valid for some TTL.)
  unset ARTIFACT_CONTENTS_URL

  pushd $workdir

  if [[ -n "${archivefile:-}" ]]; then
    unzip -n -d $workdir $archivefile || tar -C $workdir -xf $archivefile \
      && rm $archivefile || {
        echo "Failed to extract $archivefile, copying entire file."
        # Maybe it is not an archive, but a single file. Just copy.
        cp $archivefile $workdir/
      }
  fi
  if [[ -f requirements.txt ]]; then
    echo "Installing pip requirements"
    pip install -r requirements.txt
  fi
  popd

  # TODO: use separate experiment directory for named servers?
  # rm -rf /home/jovyan/exp && ln -s $expdir /home/jovyan/exp
}

if [[ -n "${ARTIFACT_CONTENTS_URL}" ]]; then
  setup_experiment_server
else
  setup_default_server
fi

# Our volume mount is at the root directory, link it in to the user's
# home directory for convenience.
rm -rf "/home/$NB_USER/work" && ln -s "$workdir" "/home/$NB_USER/work"
rsync -a /etc/jupyter/bashrc.d/ /home/$NB_USER/.bashrc.d
chown -R "$NB_USER:" "/home/$NB_USER"
chown -R "$NB_USER:" "$workdir"
set +x
