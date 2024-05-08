#!/usr/bin/env python3

from dataclasses import dataclass

import argparse
import os
import json
import logging
import re
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)

BUILD_ARGS_CACHE_FILE = ".build-args.json"
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
    logger.info(f"Found {tag_name} for {org_and_repo}, cleaning to {trimmed}")
    return trimmed


def load_build_args_from_file(path: str, github_versions: dict) -> dict:
    if path == BUILD_ARGS_CACHE_FILE:
        logger.info(f"Reusing cached build args from {path}")
    else:
        logger.info(f"Reading build args from {path}")
    with open(path, "r") as build_args_file:
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
        build_args = load_build_args_from_file(args.build_args_file, github_versions)

    if os.path.isfile(BUILD_ARGS_CACHE_FILE) and not args.build_args_file:
        build_args = load_build_args_from_file(BUILD_ARGS_CACHE_FILE, github_versions)

    if not args.skip_github and not args.build_args_file and len(build_args) == 0:
        logger.info(f"Reading GitHub versions")
        build_args = get_github_build_args(github_versions)

    if not args.skip_openshift and not args.build_args_file:
        build_args["OCP_VERSION"] = get_latest_stable_openshift_release()

    build_args["GIT_REPO"] = GIT_REPO

    build_args["GIT_REVISION"] = get_git_commit_sha()

    with open(BUILD_ARGS_CACHE_FILE, "w") as cache_file:
        logger.info(f"Caching build args to {BUILD_ARGS_CACHE_FILE}")
        json.dump(build_args, cache_file)

    return [f"{key}={val}" for key, val in build_args.items()]


def clear_image_pullspec(pullspec):
    logger.info(f"Disk space before clear:")
    subprocess.run(["df", "-h"]).check_returncode()

    args = ["podman", "image", "rm", pullspec]
    logger.info(f"Clearing {pullspec}")
    logger.info(f"$ {' '.join(args)}")
    subprocess.run(args).check_returncode()

    logger.info(f"Disk space after clear:")
    subprocess.run(["df", "-h"]).check_returncode()


@dataclass
class Image:
    containerfile: str
    pushspec: str
    build_args: list

    def __post_init__(self):
        src = f"{GIT_REPO}/tree/main/{self.containerfile}"
        self.build_args = self.build_args + [f"CONTAINERFILE_SOURCE={src}"]
        self._build_context = os.path.dirname(self.containerfile)

    @property
    def build_context(self) -> str:
        return self._build_context

    def containerfile_exists(self):
        return os.path.exists(self.containerfile) and os.path.isfile(self.containerfile)

    def __str__(self):
        return self.containerfile

    def build(self):
        args = [
            "podman",
            "build",
            "--tag",
            self.pushspec,
            "--file",
            self.containerfile,
        ]

        for build_arg in self.build_args:
            args.append("--build-arg")
            args.append(build_arg)

        build_context = f"./{self.build_context}/"

        args.append(build_context)

        logger.info(f"Building {self.containerfile}")
        logger.info(f"$ {' '.join(args)}")
        subprocess.run(args).check_returncode()

    def push(self, authfile: str):
        args = ["podman", "push", "--authfile", authfile, self.pushspec]
        logger.info(f"Pushing {self.pushspec}")
        logger.info(f"$ {' '.join(args)}")
        subprocess.run(args).check_returncode()

    def clear(self):
        clear_image_pullspec(self.pushspec)

    def get_base_images(self):
        build_arg_dict = {}
        for arg in self.build_args:
            key, val = arg.split("=")
            build_arg_dict[key] = val

        aliases = set()
        base_images = set()

        with open(self.containerfile) as containerfile:
            from_lines = [
                line.strip() for line in containerfile if line.startswith("FROM")
            ]

        for line in from_lines:
            if " as " in line:
                aliases.add(line.split(" as ")[1])
            elif " AS " in line:
                aliases.add(line.split(" AS ")[1])

        for line in from_lines:
            if line.split(" ")[1] in aliases:
                continue

            for key, val in build_arg_dict.items():
                if key in line:
                    inline_key = "$" + "{" + key + "}"
                    line = line.replace(inline_key, val)
            base_images.add(line.split(" ")[1])

        if "scratch" in base_images:
            base_images.discard("scratch")

        return base_images


def main(args):
    if args.authfile != "" and args.push_only:
        logger.error(f"Cannot combine --authfile and --push-only")
        sys.exit(1)

    if args.authfile != "":
        if not os.path.exists(args.authfile):
            logger.error(f"Authfile {args.authfile} does not exist")
            sys.exit(1)

        logger.info(f"Will push using creds in {args.authfile}")

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
    logger.info(f"Applying common build args to all builds: {common_build_args}")

    transient_images_to_build = [
        Image(
            "toolbox/Containerfile.cluster-debug-tools",
            "quay.io/zzlotnik/toolbox:cluster-debug-tools",
            common_build_args,
        ),
        Image(
            "toolbox/Containerfile.tools-fetcher",
            "quay.io/zzlotnik/toolbox:tools-fetcher",
            common_build_args,
        ),
    ]

    transient_images = frozenset(
        [image.pushspec for image in transient_images_to_build]
    )

    fedora_39_images = [
        Image(
            "toolbox/Containerfile.base",
            "quay.io/zzlotnik/toolbox:base-fedora-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "toolbox/Containerfile.kube",
            "quay.io/zzlotnik/toolbox:kube-fedora-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "toolbox/Containerfile.mco",
            "quay.io/zzlotnik/toolbox:mco-fedora-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
        Image(
            "fedora-silverblue/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-silverblue-39",
            common_build_args + ["FEDORA_VERSION=39"],
        ),
    ]

    fedora_40_images = [
        Image(
            "toolbox/Containerfile.base",
            "quay.io/zzlotnik/toolbox:base-fedora-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "toolbox/Containerfile.kube",
            "quay.io/zzlotnik/toolbox:kube-fedora-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "toolbox/Containerfile.mco",
            "quay.io/zzlotnik/toolbox:mco-fedora-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "fedora-coreos/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-coreos",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
        Image(
            "fedora-silverblue/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-silverblue-40",
            common_build_args + ["FEDORA_VERSION=40"],
        ),
    ]

    standalone_images = [
        Image(
            "devex/Containerfile.buildah",
            "quay.io/zzlotnik/devex:buildah",
            common_build_args,
        ),
        Image(
            "devex/Containerfile.epel",
            "quay.io/zzlotnik/devex:epel",
            common_build_args,
        ),
        Image(
            "ocp-ssh-debug/Containerfile",
            "quay.io/zzlotnik/testing:ssh-debug-pod",
            common_build_args,
        ),
    ]

    image_batches = [
        transient_images_to_build,
        fedora_39_images,
        fedora_40_images,
        standalone_images,
    ]

    for image_batch in image_batches:
        for image in image_batch:
            if image.containerfile_exists():
                logger.info(f"Containerfile source: {image.containerfile}")
                logger.info(f"Build context: {image.build_context}")
                logger.info(f"Pushspec: {image.pushspec}")
                logger.info(f"Base images: {image.get_base_images()}")
                logger.info(f"Build args (may not be accurate): {image.build_args}")
                logger.info(f"Is transient: {image.pushspec in transient_images}")
                logger.info("")
            else:
                logger.error(f"Missing containerfile for {image}")
                sys.exit(1)

    if not args.validate_only:
        for image_batch in image_batches:
            batch_base_images = set()

            for image in image_batch:
                batch_base_images.update(image.get_base_images())
                image.build()

                if args.authfile and image.pushspec not in transient_images:
                    image.push(args.authfile)

                if args.clear_images and image.pushspec not in transient_images:
                    image.clear()

            if args.clear_images:
                for base_image in batch_base_images:
                    if base_image not in transient_images:
                        clear_image_pullspec(base_image)

    if os.path.exists(BUILD_ARGS_CACHE_FILE) and not args.no_clear_build_args_cache:
        os.remove(BUILD_ARGS_CACHE_FILE)
        logger.info(f"Removed {BUILD_ARGS_CACHE_FILE}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
    console.setFormatter(formatter)
    logging.getLogger(__file__).addHandler(console)

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
        help="Push the local tags, if found",
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
        help="Skip OpenShift version check",
    )

    parser.add_argument(
        "--clear-images",
        dest="clear_images",
        action="store_true",
        default=False,
        help="Clear images after build to conserve disk space (primarily for GitHub Actions)",
    )

    parser.add_argument(
        "--build-args-file",
        dest="build_args_file",
        action="store",
        default=None,
        help='Path to a build args JSON file containing build args in the form of {"arg1": "val1", "arg2": "val2"}',
    )

    parser.add_argument(
        "--validate-only",
        dest="validate_only",
        action="store_true",
        default=False,
        help="Validates that the Containerfiles are present and prints all data from them, excluding build args.",
    )

    parser.add_argument(
        "--no-clear-build-args-cache",
        dest="no_clear_build_args_cache",
        action="store_true",
        default=False,
        help="Skips removing the build args cache file at the end.",
    )

    args = parser.parse_args()

    main(args)
