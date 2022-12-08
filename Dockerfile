FROM jupyter/minimal-notebook:lab-3.4.7 as base

USER root

#
# Additional packages
#

RUN apt-get update --yes && \
  apt-get install --yes --no-install-recommends \
  # Stuff for pip install
  build-essential \
  python3-dev \
  libffi-dev \
  # Common useful utilities
  git \
  nano-tiny \
  tzdata \
  unzip \
  vim-tiny \
  curl \
  dnsutils \
  jq \
  moreutils \
  # git-over-ssh
  openssh-client \
  rsync && \
  apt-get clean && rm -rf /var/lib/apt/lists/*


# JupyterLab extensions
#
# Notebook dependencies
# (Includes Notebook server extension dependencies)
#
COPY scripts/requirements.txt /tmp/notebook-requirements.txt
RUN python3 -m pip install --no-cache -r /tmp/notebook-requirements.txt
RUN rm -f /tmp/notebook-requirements.txt

#
# Enable server extensions
#

RUN python3 -m bash_kernel.install

FROM base as release

COPY scripts/chi-requirements.txt /tmp/chi-requirements.txt

ARG openstack_release=xena
RUN curl -L -Sso /upper-constraints.txt "https://raw.githubusercontent.com/openstack/requirements/stable/${openstack_release}/upper-constraints.txt"
# Unconstrained *client to avoid issues with git install
RUN python3 -m pip install --no-cache -r /tmp/chi-requirements.txt -c <(grep -v -E 'pyzmq|packaging|blazarclient|heatclient|zunclient' /upper-constraints.txt)
RUN rm -f /tmp/chi-requirements.txt /upper-constraints.txt

# FIXME(jason): this should not be necessary, it should automatically be enabled on install.
RUN jupyter serverextension enable jupyterlab_chameleon

#
# Notebook start hooks
#

COPY scripts/start-notebook.d/* /usr/local/bin/start-notebook.d/
COPY scripts/before-notebook.d/* /usr/local/bin/before-notebook.d/

# Everything in serverroot gets copied to the user's working directory on start
RUN mkdir -p /etc/jupyter/serverroot
COPY scripts/serverroot/* /etc/jupyter/serverroot/

COPY scripts/bashrc.d /etc/jupyter/bashrc.d
#RUN chown eovyan:100 -R /home/jovyan/.bashrc.d
#COPY scripts/start-notebook-dev.sh /usr/local/bin/

#RUN mkdir -p /data && chown jovyan:100 -R /data

FROM release as dev

COPY . /ext
RUN pip install /ext
#RUN mkdir -p /work
