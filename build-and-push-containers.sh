#!/usr/bin/env bash

set -xeuo

creds_path="$1"

podman pull registry.fedoraproject.org/fedora-toolbox:39
podman pull registry.fedoraproject.org/fedora:latest

podman build --build-arg-file=<(./get-versions-for-build-args.sh) -t quay.io/zzlotnik/toolbox:tools --file=./toolbox/Containerfile.tools .

declare -rA images=(
  ["./toolbox/Containerfile.base"]="quay.io/zzlotnik/toolbox:base"
  ["./toolbox/Containerfile.neovim"]="quay.io/zzlotnik/toolbox:neovim"
  ["./ocp-ssh-debug/Containerfile"]="quay.io/zzlotnik/testing:ssh-debug-pod"
  ["./silverblue/Containerfile"]="quay.io/zzlotnik/toolbox:silverblue"
)

containerfiles=(
  ./toolbox/Containerfile.base
  ./toolbox/Containerfile.neovim
  ./ocp-ssh-debug/Containerfile
  ./silverblue/Containerfile
)

for containerfile in "${containerfiles[@]}"; do
  tag="${images[${containerfile}]}"
  podman build -t "$tag" --file "$containerfile" .
done

for containerfile in "${containerfiles[@]}"; do
  tag="${images[${containerfile}]}"
  podman push --authfile="$creds_path" "$tag"
done
