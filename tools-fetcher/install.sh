#!/usr/bin/env bash

set -xeuo

repos=(
  "block/goose"
  "coreos/ignition"
  "coreos/butane"
  "derailed/k9s"
  "ericchiang/pup"
  "getantibody/antibody"
  "gmeghnag/omc"
  "golangci/golangci-lint"
  "hairyhenderson/gomplate"
  "homeport/dyff"
  "twpayne/chezmoi"
  "wagoodman/dive"
)

root_path="/out"

mkdir -p "$root_path/yq"
dra download -a mikefarah/yq -o "$root_path/yq/yq" --install-file "yq_linux_$(get-arch --amd64 --arm64)"

for repo in "${repos[@]}"; do
  name="$(basename "$repo")"
  mkdir -p "$root_path/$name"
  dra download -a "$repo" -o "$root_path/$name/$name" --install-file "$name"
done

mv "$root_path/ignition/ignition" "$root_path/ignition/ignition-validate"

mkdir -p "$root_path/oc"
cd "$root_path/oc"
curl -L "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux$(get-arch --custom-x86_64="" --custom-aarch64='-arm64')".tar.gz | tar xz
find "$root_path" -type f -executable -exec mv {} "/usr/local/bin/" \;
rm -rf "$root_path"
rm /usr/local/bin/get-arch
