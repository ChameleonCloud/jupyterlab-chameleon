if ! grep -q "bashrc.d includes" ~/.bashrc; then
  cat >> ~/.bashrc <<'EOF'

# bashrc.d includes
if [[ -d ~/.bashrc.d ]]; then
  for f in $(find ~/.bashrc.d \( -type f -o -type l \) -print | sort); do
    source "$f"
  done
fi
EOF
fi
