#!/usr/bin/env bash

set -xeuo

creds_path="${1:-}"

base_images=(
  registry.fedoraproject.org/fedora-toolbox:39
  registry.fedoraproject.org/fedora:latest
  quay.io/fedora/fedora-coreos:stable
  quay.io/fedora/fedora-silverblue:39
)

declare -rA images=(
  ["toolbox/Containerfile.tools"]="quay.io/zzlotnik/toolbox:tools"
  ["toolbox/Containerfile.base"]="quay.io/zzlotnik/toolbox:base"
  ["toolbox/Containerfile.kube"]="quay.io/zzlotnik/toolbox:kube"
  ["ocp-ssh-debug/Containerfile"]="quay.io/zzlotnik/testing:ssh-debug-pod"
  ["fedora-coreos/Containerfile"]="quay.io/zzlotnik/os-images:fedora-coreos"
  ["fedora-silverblue/Containerfile"]="quay.io/zzlotnik/os-images:fedora-silverblue"
)

containerfiles_to_build=(
  toolbox/Containerfile.tools
  toolbox/Containerfile.base
  toolbox/Containerfile.kube
  ocp-ssh-debug/Containerfile
  fedora-coreos/Containerfile
  fedora-silverblue/Containerfile
)

containerfiles_to_push=(
  toolbox/Containerfile.base
  toolbox/Containerfile.kube
  ocp-ssh-debug/Containerfile
  fedora-coreos/Containerfile
  fedora-silverblue/Containerfile
)

for base_image in "${base_images[@]}"; do
  podman pull "$base_image"
done

git_repo="https://github.com/cheesesashimi/containerfiles"
build_arg_file="$(mktemp -d)/build-args"
./get-versions-for-build-args.sh > "$build_arg_file"
echo "GIT_REVISION=$(git rev-parse HEAD)" >> "$build_arg_file"
echo "GIT_REPO=$git_repo" >> "$build_arg_file"

for containerfile in "${containerfiles_to_build[@]}"; do
  tag="${images[${containerfile}]}"
  podman build \
    --tag "$tag" \
    --file "$containerfile" \
    --build-arg-file="$build_arg_file" \
    --build-arg=CONTAINERFILE_SOURCE="$git_repo/tree/main/$containerfile" \
      "$PWD/$(dirname "$containerfile")"
done

if [[ -n "$creds_path" ]] && [[ -d "$creds_path" ]]; then
  for containerfile in "${containerfiles_to_push[@]}"; do
    tag="${images[${containerfile}]}"
    podman push --authfile="$creds_path" "$tag"
  done
fi

rm -rf "$(dirname "$build_arg_file")"
