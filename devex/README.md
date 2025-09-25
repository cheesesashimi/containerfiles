# devex

These containers are primarily used for devex purposes either locally or in a sandbox cluster.

## `quay.io/zzlotnik/devex:epel`

This image has the Centos Stream 9 EPEL repos pre-enabled. This image is
primarily intended to be used as an input into my
[`onclustertesting`](https://github.com/cheesesashimi/zacks-openshift-helper)
helper. This is why it only contains those two directories and is based on a scratch image.

## `quay.io/zzlotnik/devex:buildah`

This image takes the base `quay.io/buildah/stable:latest` image and installs
some additional packages. It's primarily intended for use in debugging and
development with running Buildah inside an OpenShift cluster. Consequently, I
have not overridden the labels provided by the base Buildah image bacause they
contain more valuable information than what I would override them with.

## `quay.io/zzlotnik/devex:zacks-openshift-helpers`

My OpenShift helpers have been migrated to the
[MCO](https://github.com/openshift/machine-config-operator) repository. Because
it is a bit more difficult to produce a standalone image from that repository,
I have opted to produce them here instead.
