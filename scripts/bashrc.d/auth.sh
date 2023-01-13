# Install wrapper functions that perform lazy refresh of access tokens.
# Access tokens have a relatively short TTL and can expire quickly.

_with_token() {
  access_token=$(curl -s -H"authorization: token $JUPYTERHUB_API_TOKEN" \
    "$JUPYTERHUB_API_URL/users/$JUPYTERHUB_USER" \
    | jq -r .auth_state.access_token)
  if [[ "$access_token" != "null" ]]; then
    export OS_ACCESS_TOKEN="$access_token"
  fi
  command "$@"
}
export -f _with_token

alias openstack='_with_token openstack'
alias blazar='_with_token blazar'
# Users shouldn't really be using this, but they try sometimes.
alias swift='_with_token swift'

if [[ -n "${OS_PROJECT_NAME+set}" ]]; then
  # Print project information in bold and blue so that it is noticeable
  echo -e "\e[1mWorking on project \e[34;1m${OS_PROJECT_NAME}\e[;1m.\e[0m"
  echo -e "\e[1mTo use a different project, set the \e[34;1mOS_PROJECT_NAME\e[;1m environment variable.\e[0m"
else
  echo -e "\e[31;1mThere is currently no project set! \e[0m"
  echo -e "\e[1mPlease set the \e[34;1mOS_PROJECT_NAME\e[;1m environment variable.\e[0m"
fi
