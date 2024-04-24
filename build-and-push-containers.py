#!/usr/bin/env python3

import argparse
import os
import json
import re
import subprocess
import sys

GIT_REPO = "https://github.com/cheesesashimi/containerfiles"
VERSION_REGEX = re.compile(r"^v[0-9].*$")


def get_github_build_args(github_versions: dict) -> dict:
    out = {}

    for arg, org_and_repo in github_versions.items():
        out[arg] = get_latest_github_release_version(org_and_repo)

    return out


def get_latest_stable_openshift_release() -> str:
    url = "https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/stable/release.txt"
    cmd = subprocess.run(["curl", "-s", url], capture_output=True)
    cmd.check_returncode()
    for line in cmd.stdout.decode("utf-8").split("\n"):
        if "Version:" in line:
            return line.replace("Version:", "").strip()


def get_git_commit_sha() -> str:
    cmd = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True)
    cmd.check_returncode()
    return cmd.stdout.decode("utf-8").strip()


def trim_vee(arg: str) -> str:
    if not VERSION_REGEX.match(arg):
        return arg

    return arg[1:]


def get_latest_github_release_version(org_and_repo: str) -> str:
    url = f"https://api.github.com/repos/{org_and_repo}/releases/latest"
    cmd = subprocess.run(["curl", "-s", url], capture_output=True)
    cmd.check_returncode()
    tag_name = json.loads(cmd.stdout)["tag_name"]
    trimmed = trim_vee(tag_name)
    print(f"Found {tag_name} for {org_and_repo}, cleaning to {trimmed}")
    return trimmed


def load_build_args_from_file(path: str, github_versions: dict) -> dict:
    with open(args.build_args_file, "r") as build_args_file:
        build_args = json.load(build_args_file)

    for arg, val in build_args.items():
        if arg in github_versions:
            build_args[arg] = trim_vee(val)

    return build_args


def get_common_build_args(args, github_versions: dict) -> list:
    if args.push_only:
        return []

    build_args = {}
    if args.build_args_file:
        print(f"Reading build args from {args.build_args_file}")
        build_args = load_build_args_from_file(args.build_args_file, github_versions)

    if not args.skip_github and not args.build_args_file:
        print(f"Reading GitHub versions")
        build_args = get_github_build_args(github_versions)

    build_args["GIT_REPO"] = GIT_REPO

    if not args.skip_openshift and not args.build_args_file:
        build_args["OCP_VERSION"] = get_latest_stable_openshift_release()

    build_args["GIT_REVISION"] = get_git_commit_sha()
    return [f"{key}={val}" for key, val in build_args.items()]


class Image(object):
    def __init__(self, containerfile: str, pushspec: str, build_args: list):
        self._containerfile = containerfile
        self._pushspec = pushspec
        src = f"{GIT_REPO}/tree/main/{containerfile}"
        self._build_args = build_args + [f"CONTAINERFILE_SOURCE={src}"]

    def build(self):
        args = [
            "podman",
            "build",
            "--tag",
            self._pushspec,
            "--file",
            self._containerfile,
        ]

        for build_arg in self._build_args:
            args.append("--build-arg")
            args.append(build_arg)

        build_context = os.path.dirname(self._containerfile)
        build_context = f"./{build_context}/"

        args.append(build_context)

        print(f"Building {self._containerfile}")
        subprocess.run(args).check_returncode()

    def push(self, authfile: str):
        args = ["podman", "push", "--authfile", authfile, self._pushspec]
        print(f"Pushing {self._pushspec}")
        subprocess.run(args).check_returncode()


def pull_base_image(base_image: str):
    subprocess.run(["podman", "pull", base_image]).check_returncode()


def main(args):
    if args.push_only and not args.authfile:
        print(f"Must set --authfile when --push-only is set")
        sys.exit(1)

    github_versions = {
        "ANTIBODY_VERSION": "getantibody/antibody",
        "CHEZMOI_VERSION": "twpayne/chezmoi",
        "DIVE_VERSION": "wagoodman/dive",
        "DYFF_VERSION": "homeport/dyff",
        "GOLANGCI_LINT_VERSION": "golangci/golangci-lint",
        "K9S_VERSION": "derailed/k9s",
        "OMC_VERSION": "gmeghnag/omc",
        "YQ_VERSION": "mikefarah/yq",
        "ZACKS_HELPERS_VERSION": "cheesesashimi/zacks-openshift-helpers",
    }

    common_build_args = get_common_build_args(args, github_versions)
    print(f"Applying common build args to all builds: {common_build_args}")

    images = [
        Image(
            "toolbox/Containerfile.tools",
            "quay.io/zzlotnik/toolbox:tools-fedora-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "toolbox/Containerfile.tools",
            "quay.io/zzlotnik/toolbox:tools-fedora-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "toolbox/Containerfile.base",
            "quay.io/zzlotnik/toolbox:base-fedora-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "toolbox/Containerfile.base",
            "quay.io/zzlotnik/toolbox:base-fedora-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "toolbox/Containerfile.kube",
            "quay.io/zzlotnik/toolbox:kube-fedora-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "toolbox/Containerfile.kube",
            "quay.io/zzlotnik/toolbox:kube-fedora-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "ocp-ssh-debug/Containerfile",
            "quay.io/zzlotnik/testing:ssh-debug-pod",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "fedora-coreos/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-coreos",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "fedora-silverblue/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-silverblue-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "fedora-silverblue/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-silverblue-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
    ]

    base_images = [
        "registry.fedoraproject.org/fedora-toolbox:39",
        "registry.fedoraproject.org/fedora-toolbox:40",
        "registry.fedoraproject.org/fedora:latest",
        "quay.io/fedora/fedora-coreos:stable",
        "quay.io/fedora/fedora-silverblue:39",
        "quay.io/fedora/fedora-silverblue:40",
    ]

    if not args.no_image_pull and not args.push_only:
        for base_image in base_images:
            pull_base_image(base_image)

    if not args.push_only:
        for image in images:
            image.build()

    if args.authfile:
        for image in images[2:]:
            image.push(args.authfile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="Builds and pushes the Containerfiles found in this repository",
    )

    parser.add_argument(
        "--authfile",
        dest="authfile",
        action="store",
        default="",
        help="Path to the authfile for pushing the images",
    )

    parser.add_argument(
        "--no-image-pull",
        dest="no_image_pull",
        action="store_true",
        default=False,
        help="Skip pulling the base images before building",
    )

    parser.add_argument(
        "--push-only",
        dest="push_only",
        action="store_true",
        default=False,
        help="Only push images",
    )

    parser.add_argument(
        "--skip-github",
        dest="skip_github",
        action="store_true",
        default=False,
        help="Skip GitHub version check",
    )

    parser.add_argument(
        "--skip-openshift",
        dest="skip_openshift",
        action="store_true",
        default=False,
        help="Skip GitHub version check",
    )

    parser.add_argument(
        "--build-args-file",
        dest="build_args_file",
        action="store",
        default=None,
        help='Path to a build args JSON file containing build args in the form of {"arg1": "val1", "arg2": "val2"}',
    )

    args = parser.parse_args()

    main(args)
