#!/usr/bin/env bash

set -xeuo

creds_path="${1:-}"

# Base images to pull first.
base_images=(
  registry.fedoraproject.org/fedora-toolbox:39
  registry.fedoraproject.org/fedora:latest
  quay.io/fedora/fedora-coreos:stable
  quay.io/fedora/fedora-silverblue:39
)

# Associates a Containerfile to a tag.
declare -rA images=(
  ["toolbox/Containerfile.tools"]="quay.io/zzlotnik/toolbox:tools"
  ["toolbox/Containerfile.base"]="quay.io/zzlotnik/toolbox:base"
  ["toolbox/Containerfile.kube"]="quay.io/zzlotnik/toolbox:kube"
  ["ocp-ssh-debug/Containerfile"]="quay.io/zzlotnik/testing:ssh-debug-pod"
  ["fedora-coreos/Containerfile"]="quay.io/zzlotnik/os-images:fedora-coreos"
  ["fedora-silverblue/Containerfile"]="quay.io/zzlotnik/os-images:fedora-silverblue"
)

# The Containerfiles in this list are built in order since it is possible that
# some images must be built before others.
containerfiles_to_build=(
  toolbox/Containerfile.tools
  toolbox/Containerfile.base
  toolbox/Containerfile.kube
  ocp-ssh-debug/Containerfile
  fedora-coreos/Containerfile
  fedora-silverblue/Containerfile
)

# The Containerfiles in this list are pushed in order, though it doesn't really
# matter what order they're pushed in.
#
# NOTE: toolbox/Containerfile.tools is purposely omitted from this list since
# its an ephemeral container that is only useful for pre-fetching and caching
# certain files for later use.
containerfiles_to_push=(
  toolbox/Containerfile.base
  toolbox/Containerfile.kube
  ocp-ssh-debug/Containerfile
  fedora-coreos/Containerfile
  fedora-silverblue/Containerfile
)

# Pull all of the base images.
for base_image in "${base_images[@]}"; do
  podman pull "$base_image"
done

# Gets the version information for the tools image and stores it in a build-arg
# file in a temp directory.
git_repo="https://github.com/cheesesashimi/containerfiles"
build_arg_file="$(mktemp -d)/build-args"
./get-versions-for-build-args.sh > "$build_arg_file"
echo "GIT_REVISION=$(git rev-parse HEAD)" >> "$build_arg_file"
echo "GIT_REPO=$git_repo" >> "$build_arg_file"

# Builds each Containerfile in order. It passes in the Containerfiles'
# directory (obtained by dirname) as the build context for each container. This
# allows container-specific files and scripts to be accessible to the build
# context.
for containerfile in "${containerfiles_to_build[@]}"; do
  tag="${images[${containerfile}]}"
  podman build \
    --tag "$tag" \
    --file "$containerfile" \
    --build-arg-file="$build_arg_file" \
    --build-arg=CONTAINERFILE_SOURCE="$git_repo/tree/main/$containerfile" \
      "$PWD/$(dirname "$containerfile")"
done

# If the path to an authfile is provided, push each image.
if [[ -n "$creds_path" ]] && [[ -d "$creds_path" ]]; then
  for containerfile in "${containerfiles_to_push[@]}"; do
    tag="${images[${containerfile}]}"
    podman push --authfile="$creds_path" "$tag"
  done
fi

# Clean up the build-arg file and its temp directory.
rm -rf "$(dirname "$build_arg_file")"
