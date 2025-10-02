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

mkdir -p /yq
dra download -a mikefarah/yq -o /yq/yq --install-file "yq_linux_$(get-arch --amd64 --arm64)"

for repo in "${repos[@]}"; do
  name="$(basename "$repo")"
  mkdir -p "/$name"
  dra download -a "$repo" -o "/$name/$name" --install-file "$name"
done

mv /ignition/ignition /ignition/ignition-validate

mkdir -p /oc
cd /oc
curl -L "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux$(get-arch --custom-x86_64="" --custom-aarch64='-arm64')".tar.gz | tar xz
