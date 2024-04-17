#!/usr/bin/env bash

set -xeuo

creds_path="$1"

base_images=(
  registry.fedoraproject.org/fedora-toolbox:39
  registry.fedoraproject.org/fedora:latest
  quay.io/fedora/fedora-coreos:stable
  quay.io/fedora/fedora-silverblue:39
)

declare -rA images=(
  ["./toolbox/Containerfile.tools"]="quay.io/zzlotnik/toolbox:tools"
  ["./toolbox/Containerfile.base"]="quay.io/zzlotnik/toolbox:base"
  ["./ocp-ssh-debug/Containerfile"]="quay.io/zzlotnik/testing:ssh-debug-pod"
  ["./fedora-coreos/Containerfile"]="quay.io/zzlotnik/os-images:fedora-coreos"
  ["./silverblue/Containerfile"]="quay.io/zzlotnik/os-images:silverblue"
)

containerfiles_to_build=(
  ./toolbox/Containerfile.tools
  ./toolbox/Containerfile.base
  ./ocp-ssh-debug/Containerfile
  ./fedora-coreos/Containerfile
  ./silverblue/Containerfile
)

containerfiles_to_push=(
  ./toolbox/Containerfile.base
  ./ocp-ssh-debug/Containerfile
  ./fedora-coreos/Containerfile
  ./silverblue/Containerfile
)

for base_image in "${base_images[@]}"; do
  podman pull "$base_image"
done

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
