#!/usr/bin/env bash

# Set up the SSH agent
if [[ -z "$SSH_AGENT_SOCK" ]]; then
  eval $(ssh-agent)
  ssh-add "/work/.ssh/id_rsa"
fi
