# toolbox

These containers are primarily intended for use with
[Toolbx](https://github.com/containers/toolbox) though using it is not a
requirement.

## Pullspecs

These containers may be pulled from:

- `quay.io/zzlotnik/toolbox:base-fedora-39`
- `quay.io/zzlotnik/toolbox:base-fedora-40`
- `quay.io/zzlotnik/toolbox:kube-fedora-39`
- `quay.io/zzlotnik/toolbox:kube-fedora-40`
- `quay.io/zzlotnik/toolbox:mco-fedora-39`
- `quay.io/zzlotnik/toolbox:mco-fedora-40`


## Usage with Toolbx

If you're using Toolbx, you do something like this:

```console
$ toolbox create --image quay.io/zzlotnik/toolbox:base-fedora-39 workspace
$ toolbox enter workspace
```

To periodically update your Toolbx environment, you can use something like this
Bash script:

```bash
#!/usr/bin/env bash

set -euo

image="quay.io/zzlotnik/toolbox:base-fedora-39"
workspace"$(whoami)-workspace"

podman stop "$workspace"
podman rm "$workspace"
podman pull "$image"
toolbox create --image "$image" "$workspace"
toolbox enter "$workspace"
```

Toolbx is not a requirement to use these images. It does make things certain
things easier. The only hard requirement is that you have a container runtime
such as [Podman](https://podman.io).

## Notes

Containers are automatically built for both Fedora 39 and Fedora 40 using the
same Containerfiles. Here is a description of what each Containerfile is used
for:

- `Containerfile.base` - This includes my preferred editor (Neovim) and all of
  the tools and runtimes needed for my plugins to work. It also includes tmux,
  Starship.rs, ZSH and all of the bits that make my CLI experience better. It
  also includes my favorite tools for working with Kubernetes (described
  separately below). Consequently, this image is the largest in this repository.
- `Containerfile.kube` - This solely includes my favorite Kubernetes tools and
  nothing that is not provided by the base image.
- `Containerfile.tools` - This is intended to be a transient container used to
  fetch my favorite tools that are not otherwise packaged so that I can
  directly copy them from this container into other containers at build-time.
  Right now, it is built and pushed as
  `quay.io/zzlotnik/toolbos:tools-fedora-{39,40}`, though it is not intended
  for consumption by anything other than a container build process. This
  pullspec will eventually become nonexistent.
- `Containerfile.mco` - This image contains everything included in
  `Containerfile.kube` as well as my [`OpenShift Helpers`](https://github.com/cheesesashimi/zacks-openshift-helpers). These
  are tools I've personally written to assist in my day-to-day work on the
  OpenShift [Machine Config Operator](https://github.com/openshift/machine-config-operator). These tools
  are not intended to be used by an end-user of the OpenShift platform and can
  easily lead to cluster instability when used incorrectly. You have been
  warned :smile:.

## Kubernetes Tools

- [`dyff`](https://github.com/homeport/dyff) - A JSON / YAML aware diffing tool.
- [`k9s`](https://github.com/derailed/k9s) - Cool `top`-like display for your Kubernetes cluster.
- [`omc`](https://github.com/gmeghnani/omc) - Useful if you work with must-gather reports from OpenShift.
- [`yq`](https://github.com/mikefarah/yq) - A CLI YAML parsing tool.
- `oc` - OpenShift CLI tool.
- `kubectl` - Kubernetes CLI tool.
