#!/usr/bin/env bash

set -euo

get_commit_for_tag() {
  tag_name="$1"
  org_and_repo="$2"
  curl -s "https://api.github.com/repos/$org_and_repo/git/ref/tags/$tag_name" | jq -r '.object.sha'
}

get_latest_github_release_version() {
  build_arg_name="$1"
  org_and_repo="$2"
  version="$(curl -s "https://api.github.com/repos/$org_and_repo/releases/latest" | jq -r '.tag_name')"
  echo "$build_arg_name=${version/v/}"
}

get_latest_stable_openshift_release() {
  build_arg_name="$1"
  version="$(curl -s 'https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/stable/release.txt' | grep "Version:" | sed 's/Version\://g' | sed 's/ //g')"
  echo "$build_arg_name=$version"
}

declare -rA github_versions=(
  ["ANTIBODY_VERSION"]="getantibody/antibody"
  ["CHEZMOI_VERSION"]="twpayne/chezmoi"
  ["DIVE_VERSION"]="wagoodman/dive"
  ["DYFF_VERSION"]="homeport/dyff"
  ["GOLANGCI_LINT_VERSION"]="golangci/golangci-lint"
  ["K9S_VERSION"]="derailed/k9s"
  ["OMC_VERSION"]="gmeghnag/omc"
  ["YQ_VERSION"]="mikefarah/yq"
  ["ZACKS_HELPERS_VERSION"]="cheesesashimi/zacks-openshift-helpers"
)

for var in "${!github_versions[@]}"; do
  build_arg="$var"
  org_and_repo="${github_versions[${var}]}"

  get_latest_github_release_version "$build_arg" "$org_and_repo"
done

get_latest_stable_openshift_release "OCP_VERSION"
