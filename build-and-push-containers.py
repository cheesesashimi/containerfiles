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
VERSION_REGEX = re.compile(r"^v[0-9].*$")


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


def get_latest_commit_from_github(org_and_repo: str, branch: str) -> str:
    path = f"/repos/{org_and_repo}/commits/{branch}"
    results = curl_or_github_cli(path)
    return results["sha"]


def get_sha_for_github_tag(org_and_repo: str, tag: str) -> str:
    path = f"/repos/{org_and_repo}/git/ref/tags/{tag}"
    results = curl_or_github_cli(path)
    return results["object"]["sha"]


def get_latest_github_release_version(org_and_repo: str) -> tuple[str, str]:
    path = f"/repos/{org_and_repo}/releases/latest"
    results = curl_or_github_cli(path)
    return results["tag_name"]


def curl_or_github_cli(path: str) -> dict:
    url = f"https://api.github.com{path}"
    args = ["curl", "-s", url]
    if shutil.which("gh"):
        logger.info(f"Using GitHub CLI for request for {path}")
        args = ["gh", "api", path]
    else:
        logger.info(f"Using curl for request {path}")

    cmd = subprocess.run(args, capture_output=True)
    cmd.check_returncode()
    return json.loads(cmd.stdout)


def clear_image_pullspec(pullspec):
    logger.info(f"Disk space before clear:")
    subprocess.run(["df", "-h"]).check_returncode()

    args = ["podman", "image", "rm", pullspec]
    logger.info(f"Clearing {pullspec}")
    logger.info(f"$ {' '.join(args)}")
    subprocess.run(args).check_returncode()

    logger.info(f"Disk space after clear:")
    subprocess.run(["df", "-h"]).check_returncode()


def get_github_labels_for_repo(org_and_repo: str, tag: str = None, commit: str = None):
    org, repo = org_and_repo.split("/")
    url_label = f"com.github.{org}.{repo}"

    out = [
        f"{url_label}=https://github.com/{org_and_repo}",
    ]

    if tag:
        out.append(f"{url_label}.tag={tag}")

    if commit:
        out.append(f"{url_label}.ref={commit}")

    return out


@dataclass
class GithubPackage:
    name: str
    org_and_repo: str

    def __post_init__(self):
        self._cachefile_name = f"{self.name}.json"
        if os.path.exists(self._cachefile_name):
            with open(self._cachefile_name, "r") as cachefile:
                loaded = json.load(cachefile)
                self._latest_tag = loaded.get("latest_tag", "")
                self._commit = loaded.get("commit", "")
        else:
            self._latest_tag = ""
            self._commit = ""

    def delete_cachefile(self):
        os.remove(self._cachefile_name)

    def _cache(self):
        data = {
            "name": self.name,
            "org_and_repo": self.org_and_repo,
            "commit": self._commit,
            "latest_tag": self._latest_tag,
        }

        with open(self._cachefile_name, "w") as cachefile:
            json.dump(data, cachefile)

    def latest_tag(self) -> str:
        if self._latest_tag != "":
            return self._latest_tag

        self._latest_tag = get_latest_github_release_version(self.org_and_repo)
        self._cache()
        return self._latest_tag

    def commit(self) -> str:
        if self._commit != "":
            return self._commit

        self._commit = get_sha_for_github_tag(self.org_and_repo, self.latest_tag())
        self._cache()
        return self._commit

    def build_arg(self) -> str:
        upper_name = self.name.upper().replace("-", "_")
        tag = self.latest_tag()
        if VERSION_REGEX.match(tag):
            tag = tag[1:]
        return f"{upper_name}_VERSION={tag}"

    def labels(self) -> str:
        return get_github_labels_for_repo(
            self.org_and_repo, self.latest_tag(), self.commit()
        )


@dataclass
class Image:
    containerfile: str
    pushspec: str
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

        for label in self.labels:
            args.append("--label")
            args.append(label)

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


def get_toolbox_labels(container_name, fedora_version):
    return [
        'com.github.containers.toolbox="true"',
        f"name={container_name}",
        'usage="This image is meant to be used with the toolbox(1) command"',
        f"summary=Fedora {fedora_version} of {container_name}",
        'maintainer="Zack Zlotnik (zzlotnik@redhat.com)"',
    ]


def get_cluster_debug_tools_labels() -> list:
    org_and_repo = "openshift/cluster-debug-tools"
    commit = get_latest_commit_from_github(org_and_repo, "master")
    return get_github_labels_for_repo(org_and_repo, None, commit)


def main(args):
    if args.authfile != "" and args.push_only:
        logger.error(f"Cannot combine --authfile and --push-only")
        sys.exit(1)

    if args.authfile != "":
        if not os.path.exists(args.authfile):
            logger.error(f"Authfile {args.authfile} does not exist")
            sys.exit(1)

        logger.info(f"Will push using creds in {args.authfile}")

    github_packages = [
        GithubPackage("antibody", "getantibody/antibody"),
        GithubPackage("chezmoi", "twpayne/chezmoi"),
        GithubPackage("dive", "wagoodman/dive"),
        GithubPackage("golangci-lint", "golangci/golangci-lint"),
        GithubPackage("k9s", "derailed/k9s"),
        GithubPackage("omc", "gmeghnag/omc"),
        GithubPackage("zacks-helpers", "cheesesashimi/zacks-openshift-helpers"),
    ]

    github_build_labels = []
    for package in github_packages:
        github_build_labels += package.labels()

    github_build_args = [package.build_arg() for package in github_packages]

    ocp_version = get_latest_stable_openshift_release()
    github_build_args.append(f"OCP_VERSION={ocp_version}")
    github_build_labels.append(f"com.openshift.version={ocp_version}")

    cluster_debug_tools_ref = get_latest_commit_from_github(
        "openshift/cluster-debug-tools", "master"
    )

    transient_images_to_build = [
        Image(
            "toolbox/Containerfile.cluster-debug-tools",
            "quay.io/zzlotnik/toolbox:cluster-debug-tools",
            [],
            get_cluster_debug_tools_labels(),
        ),
        Image(
            "toolbox/Containerfile.tools-fetcher",
            "quay.io/zzlotnik/toolbox:tools-fetcher",
            github_build_args,
            github_build_labels,
        ),
    ]

    transient_images = frozenset(
        [image.pushspec for image in transient_images_to_build]
    )

    fedora_39_images = [
        Image(
            "toolbox/Containerfile.base",
            "quay.io/zzlotnik/toolbox:base-fedora-39",
            ["FEDORA_VERSION=39"],
            get_toolbox_labels("base", "39"),
        ),
        Image(
            "toolbox/Containerfile.kube",
            "quay.io/zzlotnik/toolbox:kube-fedora-39",
            ["FEDORA_VERSION=39"],
            get_toolbox_labels("kube", "39"),
        ),
        Image(
            "toolbox/Containerfile.mco",
            "quay.io/zzlotnik/toolbox:mco-fedora-39",
            ["FEDORA_VERSION=39"],
            get_toolbox_labels("mco", "39"),
        ),
        Image(
            "fedora-silverblue/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-silverblue-39",
            ["FEDORA_VERSION=39"],
        ),
    ]

    fedora_40_images = [
        Image(
            "toolbox/Containerfile.base",
            "quay.io/zzlotnik/toolbox:base-fedora-40",
            ["FEDORA_VERSION=40"],
            get_toolbox_labels("base", "40"),
        ),
        Image(
            "toolbox/Containerfile.kube",
            "quay.io/zzlotnik/toolbox:kube-fedora-40",
            ["FEDORA_VERSION=40"],
            get_toolbox_labels("kube", "40"),
        ),
        Image(
            "toolbox/Containerfile.mco",
            "quay.io/zzlotnik/toolbox:mco-fedora-40",
            ["FEDORA_VERSION=40"],
            get_toolbox_labels("mco", "40"),
        ),
        Image(
            "fedora-coreos/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-coreos",
            ["FEDORA_VERSION=40"],
        ),
        Image(
            "fedora-silverblue/Containerfile",
            "quay.io/zzlotnik/os-images:fedora-silverblue-40",
            ["FEDORA_VERSION=40"],
        ),
    ]

    standalone_images = [
        Image(
            "devex/Containerfile.buildah",
            "quay.io/zzlotnik/devex:buildah",
        ),
        Image(
            "devex/Containerfile.epel",
            "quay.io/zzlotnik/devex:epel",
        ),
        Image(
            "ocp-ssh-debug/Containerfile",
            "quay.io/zzlotnik/testing:ssh-debug-pod",
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

    if not args.no_clear_github_cache:
        for package in github_packages:
            package.delete_cachefile()
            logger.info(f"Removed cachefile for {package.name}")


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

    parser.add_argument(
        "--no-clear-github-cache",
        dest="no_clear_github_cache",
        action="store_true",
        default=False,
        help="Skips removing the Github cache files at the end.",
    )

    args = parser.parse_args()

    main(args)
