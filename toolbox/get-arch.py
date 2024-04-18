#!/usr/bin/env python3

import argparse
import itertools
import platform
import sys


def add_custom_for_arch(arch, opts_set):
    opts_set_list = list(opts_set)
    opts_set_list.append(f"custom-{arch}")
    return frozenset(opts_set_list)


ARM64_OPTS = frozenset(
    [
        "arm64",
        "aarch64",
    ]
)

X86_64_OPTS = frozenset(
    [
        "amd64",
        "x86-64",
        "x86_64",
    ]
)

OPTS_SETS_BY_ARCH = {
    "aarch64": add_custom_for_arch("aarch64", ARM64_OPTS),
    "x86_64": add_custom_for_arch("x86_64", X86_64_OPTS),
}


def get_selected_items_for_opts_set(opts_set, vars_args):
    out = {}

    for arg, value in vars_args.items():
        if arg not in opts_set:
            continue

        if value == False or value == None:
            continue

        out[arg] = value

    return out


def is_only_one_selected(opts_set, vars_args, arch):
    vars_args_opts = get_selected_items_for_opts_set(opts_set, vars_args)

    if len(vars_args_opts) == 0:
        for_msg = sorted(list([f"--{opt}" for opt in opts_set]))
        vars_args_opts = sorted(list([f"--{opt}" for opt in vars_args_opts]))
        print(f"at least one of {for_msg} must be used, have: {vars_args_opts}")
        return False

    if len(vars_args_opts) > 1:
        print(
            f"only one {arch} option permitted per arch, found: {sorted(list(vars_args_opts))}"
        )
        return False

    return True


def get_desired_arch(vars_args):
    machine = platform.machine()

    if machine not in OPTS_SETS_BY_ARCH:
        print(f"unknown architecture {machine}, known: {OPTS_SETS_BY_ARCH.keys()}")
        sys.exit(1)

    found = get_selected_items_for_opts_set(OPTS_SETS_BY_ARCH[machine], vars_args)
    if len(found) != 1:
        print(f"options selected: {items}")
        sys.exit(1)

    arg, value = list(found.items())[0]
    if "custom" not in arg:
        return arg

    return value


def main(args):
    # https://docs.python.org/3/library/functions.html#vars
    vars_args = vars(args)

    for arch, opts_set in OPTS_SETS_BY_ARCH.items():
        if not is_only_one_selected(opts_set, vars_args, arch):
            sys.exit(1)

    print(get_desired_arch(vars_args))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outputs the system architecture in the desired format."
    )

    arches = OPTS_SETS_BY_ARCH.keys()
    for arch in arches:
        opts_set_list = sorted(list(OPTS_SETS_BY_ARCH[arch]))
        for item in opts_set_list:
            if "custom" in item:
                parser.add_argument(
                    f"--{item}",
                    action="store",
                    dest=item,
                    help=f'use custom value for "{arch}"',
                    type=str,
                )
            else:
                parser.add_argument(
                    f"--{item}",
                    dest=item,
                    action="store_true",
                    help=f'use "{item}" for "{arch}"',
                )

    main(parser.parse_args())
