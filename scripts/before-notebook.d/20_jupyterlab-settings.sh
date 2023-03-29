# Copy some overrides to a well-known location
user_settings_dir="/home/$NB_USER/.jupyter/lab/user-settings"

theme_settings="$user_settings_dir/@jupyterlab/apputils-extension/themes.jupyterlab-settings"
mkdir -p "$(dirname "$theme_settings")"
# TODO: re-enable when Chameleon theme works / has some actual value.
cat >"$theme_settings" <<EOF
{
  // Override default theme
  //"theme": "Chameleon"
}
EOF

# Ensure the NB_USER has permissions to the new files
chown -R "$NB_USER:" "/home/$NB_USER/.jupyter"
