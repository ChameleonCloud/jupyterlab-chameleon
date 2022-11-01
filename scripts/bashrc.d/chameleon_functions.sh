#!/usr/bin/env bash
# A collection of useful functions for dealing with the Chameleon
# testbed via Bash. Most things are possible with the vanilla
# OpenStack CLI, but some things are a bit trickier; namely, getting
# resources currently associated with a lease.

# use_site SITE
#
# Configures the local shell to point to the specified Chameleon site.
# This allows changing which site a command will operate against.
#
# Example:
#    use_site CHI@UC
#
use_site() {
  local site_name="$1"
  local site="$(curl --silent --location https://api.chameleoncloud.org/sites.json \
    | jq ".items | map(select(.name==\"$site_name\")) | first")"
  if [[ $? -gt 0 || "$site" == "null" ]]; then
    echo -n "Could not find site '$site_name'! Possible options are: "
    curl --silent --location https://api.chameleoncloud.org/sites.json \
      | jq -r '.items[].name' \
      | xargs echo
    return 1
  fi
  local site_url="$(jq -r .web <<<"$site")"
  export OS_AUTH_URL="${site_url}:5000/v3"
  unset OS_REGION_NAME
  cat <<EOF
Now using ${site_name}:
URL: ${site_url}
Location: $(jq -r .location <<<"$site")
Support contact: $(jq -r .user_support_contact <<<"$site")
EOF
}
export -f use_site

# lease_list_floating_ips LEASE
#
# Lists the public floating IP addresses tied to a lease, if any.
#
# Example:
#   lease_list_floating_ips my-lease
#
lease_list_floating_ips() {
  lease_id="$1"
  local reservation_id=$(blazar lease-show "$lease_id" -f json \
    | jq -r '.reservations' \
    | jq -rs 'map(select(.resource_type=="virtual:floatingip"))[].id')

  openstack floating ip list --tags "reservation:$reservation_id" \
    -f value -c "Floating IP Address"
}
export -f lease_list_floating_ips

# lease_server_create_default_args LEASE
#
# Returns a list of arguments that can be fed in to an
# `openstack server create` call. Sets up some useful
# defaults like the reservation hint (required to launch
# with a lease) and the default support image / network.
#
# Example:
#   openstack server create $(lease_server_create_default_args my-lease) my-server
#
lease_server_create_default_args() {
  local lease="$1"
  declare -a local defaults=()

  defaults+=(--flavor baremetal)
  defaults+=(--image CC-CentOS7)

  local network_id=$(openstack network show sharednet1 -f value -c id)
  defaults+=(--nic net-id=$network_id)

  local reservation_id=$(blazar lease-show "$lease" -f json \
    | jq -r '.reservations' \
    | jq -rs 'map(select(.resource_type=="physical:host"))[].id')
  defaults+=(--hint reservation=$reservation_id)

  echo "${defaults[@]}"
}
export -f lease_server_create_default_args

# lease_list_reservations LEASE
#
# Returns a JSON-encoded list of reservation objects. This can be then filtered
# further by using `jq` or some other JSON processor. This function is provided
# because the "reservations" property of a lease is a nested JSON document,
# which can be confusing to deal with.
#
# Example:
#   # List all reservations of type "physical:host"
#   jq 'map(select(.resource_type="physical:host"))' <(lease_list_reservations my-lease)
#
lease_list_reservations() {
  local lease="$1"

  blazar lease-show "$lease" -f json \
    | jq -r '.reservations' | jq -s .
}
export -f lease_list_reservations

# key_pair_upload [KEYPAIR_NAME]
#
# Uploads the public key at $OS_KEYPAIR_PUBLIC_KEY as a new key pair titled
# KEYPAIR_NAME. Will first check if a key pair already exists with this name.
# Will not override existing key pairs.
#
# Example:
#   # Creates a new key pair 'my-keypair' with public key
#   key_pair_upload my-keypair
#
key_pair_upload() {
  local default_name="${OS_KEYPAIR_NAME:-$USER-jupyter}"
  local keypair_name="${1:-$default_name}"
  local pubkey="${OS_KEYPAIR_PUBLIC_KEY:-/work/.ssh/id_rsa.pub}"
  local privkey="${OS_KEYPAIR_PRIVATE_KEY:-/work/.ssh/id_rsa}"

  if [[ ! -f "$pubkey" ]]; then
    ssh-keygen -y -f "$privkey" >"$pubkey"
  fi

  openstack keypair show "$keypair_name" 2>/dev/null \
    || openstack keypair create --public-key "$pubkey" "$keypair_name"
}
export -f key_pair_upload

# Wait helpers

wait_ssh() {
  local ip="$1"
  local timeout="${2:-300}"
  echo "Waiting up to $timeout seconds for SSH on $ip..."
  mkdir -p ~/.ssh
  timeout $timeout bash -c 'until printf "" 2>>/dev/null >>/dev/tcp/$0/$1; do sleep 1; done' "$ip" 22 \
      && ssh-keyscan -H "$ip" 2>/dev/null >> ~/.ssh/known_hosts \
      && echo "SSH is running!"
}
export -f wait_ssh

wait_lease() {
  local lease="$1"
  local timeout="${2:-300}"
  echo "Waiting up to $timeout seconds for lease $lease to start..."
  timeout $timeout bash -c 'until [[ $(blazar lease-show $0 -f value -c status) == "ACTIVE" ]]; do sleep 1; done' "$lease" \
    && echo "Lease started successfully!"
}
export -f wait_lease

wait_instance() {
  local server="$1"
  local timeout="${2:-600}"
  echo "Waiting up to $timeout seconds for instance $server to start"
  timeout $timeout bash -c 'until [[ $(openstack server show $0 -f value -c status) == "ACTIVE" ]]; do sleep 1; done' "$server" \
    && echo "Instance created successfully!"
}
export -f wait_instance

wait_stack() {
  local stack="$1"
  local timeout="${2:-1800}"
  echo "Waiting up to $timeout seconds for stack $stack to start"
  timeout $timeout bash -c 'until [[ $(openstack stack show $0 -f value -c stack_status) == "CREATE_COMPLETE" ]]; do sleep 1; done' "$stack" \
    && echo "Stack started successfully!"
}
export -f wait_stack
