# fedora-coreos

This contains my customized [Fedora CoreOS](https://fedoraproject.org/coreos/)
images that are prebuilt with all of my favorite CLI tools. I am only building
from the Fedora CoreOS stable image here.

## Usage

While you can use these images with a container runtime such as
[Podman](https://podman.io), the intended use is with [ostree native
containers](https://coreos.github.io/rpm-ostree/container/). In other words, if
you have an ostree-based system, you can rebase your system onto these images
by doing something like:

```console
$ rpm-ostree rebase ostree-unverified-registry:quay.io/zzlotnik/os-images:fedora-coreos
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
$ echo "quay.io/zzlotnik/os-images@$(skopeo inspect docker://quay.io/zzlotnik/os-images:fedora-coreos | jq -r '.Digest')"
quay.io/zzlotnik/os-images@sha256:159ed741f95346f28a96d253f986d028a16cf9e18a4d7391e76aaf53c7190416
```

(Note: Do not use the above digested pullspec as it will get garbage-collected.)

## Pullspecs

This image can be pulled from this tagged pullspec: `quay.io/zzlotnik/os-images:fedora-coreos`
