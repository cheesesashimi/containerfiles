#!/usr/bin/env bash

set -xeuo

declare -A repos=(
  ["mikefarah/yq"]="yq_linux_$(get-arch --amd64 --arm64)"
  ["ankitpokhrel/jira-cli"]="jira"
  ["block/goose"]=""
  ["coreos/ignition"]=""
  ["coreos/butane"]=""
  ["derailed/k9s"]=""
  ["ericchiang/pup"]=""
  ["getantibody/antibody"]=""
  ["gmeghnag/omc"]="omc"
  ["golangci/golangci-lint"]=""
  ["hairyhenderson/gomplate"]=""
  ["homeport/dyff"]=""
  ["twpayne/chezmoi"]=""
  ["wagoodman/dive"]=""
)

root_path="/out"

for repo in "${!repos[@]}"; do
  # Determine the name of the executable/directory
  name="$(basename "$repo")"

  # Determine the value for --install-file
  install_file_val="${repos[$repo]}"
  if [[ -z "$install_file_val" ]]; then
    # If the value is empty, use basename for the --install-file
    install_file_val="$name"
  fi

  mkdir -p "$root_path/$name"
  # Use the calculated install_file_val in the dra download command
  dra download -a "$repo" -o "$root_path/$name/$name" --install-file "$install_file_val"
done

mv "$root_path/ignition/ignition" "$root_path/ignition/ignition-validate"
mv "$root_path/jira-cli/jira-cli" "$root_path/jira-cli/jira"

mkdir -p "$root_path/oc"
cd "$root_path/oc"
curl -L "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux$(get-arch --custom-x86_64="" --custom-aarch64='-arm64')".tar.gz | tar xz
find "$root_path" -type f -executable -exec mv {} "/usr/local/bin/" \;
rm -rf "$root_path"
rm /usr/local/bin/get-arch
rm /usr/local/bin/dra
