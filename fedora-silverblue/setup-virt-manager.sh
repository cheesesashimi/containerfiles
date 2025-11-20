#!/usr/bin/env bash

# This script may need to be run multiple times and a reboot may also be
# required before virt-manager fully works.

set -xeuo

user="$1"

usermod -a -G libvirt "$user"
usermod -a -G qemu "$user"
virsh net-start default
virsh net-autostart default
restorecon -rv /var/lib/libvirt
