#!/usr/bin/env python3
"""
Generate apm.yml by walking cloned repositories and discovering all
installable skills and plugins.

Skills are any directories containing a SKILL.md file, found by walking
the given root directories recursively with os.walk.
"""

import argparse
import os
import sys

import yaml


def find_skills(root: str) -> list[str]:
    """Return absolute paths to every directory containing a SKILL.md under root."""
    skills = []
    if not os.path.isdir(root):
        print(f"Warning: {root} not found", file=sys.stderr)
        return skills
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        if "SKILL.md" in filenames:
            skills.append(dirpath)
    return skills


def generate_apm_yml(roots: list[str], output: str) -> None:
    skills = []
    for root in roots:
        found = find_skills(root)
        print(f"Found {len(found)} skills in {root}", file=sys.stderr)
        skills.extend(found)

    manifest = {
        "name": "ai-sandbox",
        "version": "1.0.0",
        "description": "Zacks AI sandbox",
        "targets": ["claude", "opencode"],
        "dependencies": {
            "apm": skills,
        },
    }

    with open(output, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Wrote {output} ({len(skills)} entries)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, metavar="DIR", action="append",
                        help="Root directory to search for skills (repeatable)")
    parser.add_argument("--output", required=True, metavar="FILE",
                        help="Output path for apm.yml")
    args = parser.parse_args()
    generate_apm_yml(args.root, args.output)


if __name__ == "__main__":
    main()
