#!/usr/bin/env python3

from dataclasses import dataclass, field

import argparse
import os
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)

GIT_REPO = "https://github.com/cheesesashimi/containerfiles"


def get_git_commit_sha() -> str:
    cmd = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True)
    cmd.check_returncode()
    return cmd.stdout.decode("utf-8").strip()


def clear_image_pullspec(pullspec):
    logger.info(f"Disk space before clear:")
    subprocess.run(["df", "-h"]).check_returncode()

    args = ["podman", "image", "rm", "--ignore", pullspec]
    logger.info(f"Clearing {pullspec}")
    logger.info(f"$ {' '.join(args)}")
    subprocess.run(args).check_returncode()

    logger.info(f"Disk space after clear:")
    subprocess.run(["df", "-h"]).check_returncode()


@dataclass
class Image:
    containerfile: str
    pushspecs: str
    build_args: list = field(default_factory=list)
    labels: list = field(default_factory=list)

    def __post_init__(self):
        git_ref = get_git_commit_sha()
        src = f"{GIT_REPO}/blob/{git_ref}/{self.containerfile}"
        self._build_context = os.path.dirname(self.containerfile)
        self.labels.append(f"org.opencontainers.image.url={GIT_REPO}")
        self.labels.append(f"org.opencontainers.image.source={src}")
        self.labels.append(f"org.opencontainers.image.revision={git_ref}")

        conditional_labels = {
            "GITHUB_ACTIONS": "com.github.actions=",
            "GITHUB_RUN_ID": "com.github.actions.runId=GITHUB_RUN_ID",
            "GITHUB_RUN_NUMBER": "com.github.actions.runNumber=GITHUB_RUN_NUMBER",
            "GITHUB_WORKFLOW": "com.github.actions.workflow=GITHUB_WORKFLOW",
            "RUNNER_NAME": "com.github.actions.runnerName=RUNNER_NAME",
        }

        for var, label in conditional_labels.items():
            value = os.getenv(var)
            if value:
                self.labels.append(label.replace(var, value))

        self._first_pushspec = self.pushspecs[0]

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
            self._first_pushspec,
            "--file",
            self.containerfile,
        ]

        for build_arg in self.build_args:
            args.append("--build-arg")
            args.append(build_arg)

        for label in self.labels:
            args.append("--label")
            args.append(label)

        build_context = f"./{self.build_context}/"

        args.append(build_context)

        logger.info(f"Building {self.containerfile}")
        logger.info(f"$ {' '.join(args)}")
        subprocess.run(args).check_returncode()

    def push(self, authfile: str):
        for pushspec in self.pushspecs:
            if pushspec != self._first_pushspec:
                args = ["podman", "tag", self._first_pushspec, pushspec]
                logger.info(f"Tagging {self._first_pushspec} as {pushspec}")
                logger.info(f"$ {' '.join(args)}")
                subprocess.run(args).check_returncode()

            args = ["podman", "push", "--authfile", authfile, pushspec]
            logger.info(f"Pushing {pushspec}")
            logger.info(f"$ {' '.join(args)}")
            subprocess.run(args).check_returncode()

    def clear(self):
        for pushspec in self.pushspecs:
            clear_image_pullspec(pushspec)

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


def get_toolbox_labels(container_name, fedora_version):
    return [
        'com.github.containers.toolbox="true"',
        f"name={container_name}",
        'usage="This image is meant to be used with the toolbox(1) command"',
        f"summary=Fedora {fedora_version} of {container_name}",
        'maintainer="Zack Zlotnik (zzlotnik@redhat.com)"',
    ]


def get_fedora_images(fedora_version):
    tag_suffix = f"fedora-{fedora_version}"

    fedora_version_build_args = [f"FEDORA_VERSION={fedora_version}"]

    return [
        Image(
            "toolbox/Containerfile.base",
            [f"quay.io/zzlotnik/toolbox:base-{tag_suffix}"],
            fedora_version_build_args,
            get_toolbox_labels("base", fedora_version),
        ),
        Image(
            "toolbox/Containerfile.kube",
            [f"quay.io/zzlotnik/toolbox:kube-{tag_suffix}"],
            fedora_version_build_args,
            get_toolbox_labels("kube", fedora_version),
        ),
        Image(
            "toolbox/Containerfile.mco",
            [f"quay.io/zzlotnik/toolbox:mco-{tag_suffix}"],
            fedora_version_build_args,
            get_toolbox_labels("mco", fedora_version),
        ),
        Image(
            "toolbox/Containerfile.podman-dev-env",
            ["quay.io/zzlotnik/toolbox:podman-dev-env"],
            fedora_version_build_args,
            get_toolbox_labels("podman-dev-env", fedora_version),
        ),
        Image(
            "toolbox/Containerfile.workspace",
            [f"quay.io/zzlotnik/toolbox:workspace-{tag_suffix}"],
            fedora_version_build_args,
            get_toolbox_labels("workspace", fedora_version),
        ),
        Image(
            "toolbox/Containerfile.ai-workspace",
            [f"quay.io/zzlotnik/toolbox:ai-workspace-{tag_suffix}"],
            fedora_version_build_args,
            get_toolbox_labels("ai-workspace", fedora_version),
        ),
        Image(
            "toolbox/Containerfile.ai-minimal",
            [f"quay.io/zzlotnik/toolbox:ai-minimal-{tag_suffix}"],
            fedora_version_build_args,
            get_toolbox_labels("ai-minimal", fedora_version),
        ),
        Image(
            "fedora-silverblue/Containerfile",
            [f"quay.io/zzlotnik/os-images:fedora-silverblue-{fedora_version}"],
            fedora_version_build_args,
        ),
    ]


def main(args):
    if args.authfile != "" and args.push_only:
        logger.error(f"Cannot combine --authfile and --push-only")
        sys.exit(1)

    if args.authfile != "":
        if not os.path.exists(args.authfile):
            logger.error(f"Authfile {args.authfile} does not exist")
            sys.exit(1)

        logger.info(f"Will push using creds in {args.authfile}")

    standalone_images = [
        Image(
            "devex/Containerfile.epel9",
            ["quay.io/zzlotnik/devex:epel", "quay.io/zzlotnik/devex:epel9"],
        ),
        Image(
            "devex/Containerfile.epel10",
            ["quay.io/zzlotnik/devex:epel10"],
        ),
        Image(
            "ocp-ssh-debug/Containerfile",
            ["quay.io/zzlotnik/testing:ssh-debug-pod"],
        ),
        Image(
            "tools-fetcher/Containerfile",
            ["quay.io/zzlotnik/toolbox:tools-fetcher"],
        ),
    ]

    image_batches = [
        standalone_images,
        get_fedora_images("42"),
        get_fedora_images("43"),
    ]

    for image_batch in image_batches:
        for image in image_batch:
            if image.containerfile_exists():
                logger.info(f"Containerfile source: {image.containerfile}")
                logger.info(f"Build context: {image.build_context}")
                logger.info(f"Pushspec(s): {image.pushspecs}")
                logger.info(f"Base images: {image.get_base_images()}")
                logger.info(f"Build args (may not be accurate): {image.build_args}")
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

                if args.authfile:
                    image.push(args.authfile)

                if args.clear_images:
                    image.clear()

            if args.clear_images:
                for base_image in batch_base_images:
                    clear_image_pullspec(base_image)


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

    args = parser.parse_args()

    main(args)
