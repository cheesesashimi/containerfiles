#!/usr/bin/env bash

set -xeuo

creds_path="$1"

podman pull registry.fedoraproject.org/fedora-toolbox:39
podman pull registry.fedoraproject.org/fedora:latest

declare -rA images=(
  ["./toolbox/Containerfile.tools"]="quay.io/zzlotnik/toolbox:tools"
  ["./toolbox/Containerfile.base"]="quay.io/zzlotnik/toolbox:base"
  ["./toolbox/Containerfile.neovim"]="quay.io/zzlotnik/toolbox:neovim"
  ["./ocp-ssh-debug/Containerfile"]="quay.io/zzlotnik/testing:ssh-debug-pod"
  ["./silverblue/Containerfile"]="quay.io/zzlotnik/toolbox:silverblue"
)

containerfiles_to_build=(
  ./toolbox/Containerfile.tools
  ./toolbox/Containerfile.base
  ./toolbox/Containerfile.neovim
  ./ocp-ssh-debug/Containerfile
  ./silverblue/Containerfile
)

containerfiles_to_push=(
  ./toolbox/Containerfile.base
  ./toolbox/Containerfile.neovim
  ./ocp-ssh-debug/Containerfile
  ./silverblue/Containerfile
)

build_arg_file="$(mktemp -d)/build-args"
./get-versions-for-build-args.sh > "$build_arg_file"
echo "GIT_REVISION=$(git rev-parse HEAD)" >> "$build_arg_file"
echo "GIT_REPO=https://github.com/cheesesashimi/containerfiles" >> "$build_arg_file"

for containerfile in "${containerfiles_to_build[@]}"; do
  tag="${images[${containerfile}]}"
  cleaned_containerfile_path="$(echo "$containerfile" | sed 's/\.\///g')"
  podman build \
    --tag "$tag" \
    --file "$containerfile" \
    --build-arg-file="$build_arg_file" \
    --build-arg=CONTAINERFILE_NAME="$cleaned_containerfile_path" \
      .
done

for containerfile in "${containerfiles_to_push[@]}"; do
  tag="${images[${containerfile}]}"
  podman push --authfile="$creds_path" "$tag"
done

rm -rf "$(dirname "$build_arg_file")"
