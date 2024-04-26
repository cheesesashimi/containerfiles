# fedora-silverblue

This contains my customized [Fedora
Silverblue](https://fedoraproject.org/atomic-desktops/silverblue/) images that
are prebuilt with all of my favorite CLI tools. Both Fedora 39 and Fedora 40
versions of this Containerfile are built automatically.

## Usage

While you can use these images with a container runtime such as
[Podman](https://podman.io), the intended use is with [ostree native
containers](https://coreos.github.io/rpm-ostree/container/). In other words, if
you have an ostree-based system, you can rebase your system onto these images
by doing something like:

```console
$ rpm-ostree rebase ostree-unverified-registry:quay.io/zzlotnik/os-images:fedora-silverblue-39
```

This will apply the image onto your machine using ostree. Post-apply, you then
reboot your machine and it boots into the newly-applied image. The previous
image is retained and can be rolled back to. For more information, see:
[ostree](https://github.com/ostreedev/ostree). 

## Digested Pullspecs

Once you've used this image with a tagged pullspec, updating to a newer image
becomes slightly more involved because `rpm-ostree` will not resolve the digest
from the tag. Instead, it will see that the pullspec is identical to the one
you've provided and refuse to rebase. To get the latest digested pullspec for
this image, you can use [Skopeo](https://github.com/containers/skopeo) and `jq`
to obtain it thusly:

```console
$ echo "quay.io/zzlotnik/os-images@$(skopeo inspect docker://quay.io/zzlotnik/os-images:fedora-silverblue-40 | jq -r '.Digest')"
quay.io/zzlotnik/os-images@sha256:fc8f49f711b74d7ded1f0511c4163be7720581b5febf7b11d0bf3660aaa22ceb
```

(Note: Do not use the above digested pullspec as it will get garbage-collected.)

## Pullspecs

These images can be pulled from the following tagged pullspecs:
- `quay.io/zzlotnik/os-images:fedora-silverblue-39`
- `quay.io/zzlotnik/os-images:fedora-silverblue-40`
