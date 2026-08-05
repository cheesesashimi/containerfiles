#!/usr/bin/env python3
"""
Synchronise the openshift-eng/ai-helpers plugin entries in apm.yml with
what is currently in the upstream repository.

For each directory found under plugins/ in the repo the script checks
whether it is installable by APM.  A plugin is considered incompatible when
its .claude-plugin/plugin.json lists dependencies that use the old Claude
marketplace format ({"name": "..."} objects without a "git" field), which
APM cannot resolve.  Incompatible plugins are skipped with a warning.

The script then reconciles the set of compatible upstream plugins with the
entries already in apm.yml:
  - Newly-added upstream plugins are inserted.
  - Plugins that have been removed upstream are deleted.
  - Plugins that are already present and still compatible are left alone.
  - Plugins that were previously skipped but are now compatible are added.

The list is kept in sorted order.  All other entries in apm.yml (e.g. the
googleworkspace/cli entry) are preserved unchanged.

Usage:
    python3 sync-ai-helpers.py [--dry-run] [--token TOKEN] [apm_yml_path]

Options:
    --dry-run          Print what would change without writing the file.
    --token TOKEN      GitHub personal access token (increases rate limits).
                       Can also be set via the GITHUB_TOKEN env variable.
    apm_yml_path       Path to apm.yml (default: apm.yml in the same
                       directory as this script).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

import yaml

REPO = "openshift-eng/ai-helpers"
PLUGINS_PATH = "plugins"
APM_PREFIX = f"{REPO}/{PLUGINS_PATH}/"
GITHUB_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _make_request(url: str, token: str | None) -> dict | list:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            sys.exit(
                f"GitHub API rate limit exceeded or access denied for {url}.\n"
                "Pass a personal access token with --token or set GITHUB_TOKEN."
            )
        raise


def list_plugin_dirs(token: str | None) -> list[str]:
    """Return the names of all subdirectories under plugins/ in the repo."""
    url = f"{GITHUB_API}/repos/{REPO}/contents/{PLUGINS_PATH}"
    entries = _make_request(url, token)
    return sorted(e["name"] for e in entries if e["type"] == "dir")


def fetch_plugin_json(plugin: str, token: str | None) -> dict | None:
    """
    Return the parsed .claude-plugin/plugin.json for a plugin, or None if
    the file does not exist.
    """
    url = (
        f"{GITHUB_API}/repos/{REPO}/contents/"
        f"{PLUGINS_PATH}/{plugin}/.claude-plugin/plugin.json"
    )
    try:
        data = _make_request(url, token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    # The API returns the file metadata; fetch raw content via download_url.
    raw_url = data.get("download_url")
    if not raw_url:
        return None
    req = urllib.request.Request(raw_url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Compatibility check
# ---------------------------------------------------------------------------

def has_incompatible_deps(plugin_json: dict) -> bool:
    """
    Return True when plugin.json declares dependencies in the old Claude
    marketplace format — {"name": "..."} without a "git" field — which APM
    cannot resolve.
    """
    for dep in plugin_json.get("dependencies", []):
        if isinstance(dep, dict) and "name" in dep and "git" not in dep:
            return True
    return False


# ---------------------------------------------------------------------------
# apm.yml manipulation
# ---------------------------------------------------------------------------

def load_apm_yml(path: str) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def save_apm_yml(path: str, data: dict) -> None:
    with open(path, "w") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)


def get_current_plugins(deps: list) -> set[str]:
    """Extract the plugin names already listed for openshift-eng/ai-helpers."""
    plugins = set()
    for entry in deps:
        if isinstance(entry, str) and entry.startswith(APM_PREFIX):
            plugins.add(entry[len(APM_PREFIX):])
    return plugins


def update_deps(deps: list, compatible: set[str]) -> tuple[list, list[str], list[str]]:
    """
    Return an updated dependency list plus the lists of added and removed
    plugin names.  Non-ai-helpers entries are preserved in their original
    positions.  The ai-helpers block is replaced with the new sorted set.
    """
    current = get_current_plugins(deps)
    added = sorted(compatible - current)
    removed = sorted(current - compatible)

    non_ai = [e for e in deps if not (isinstance(e, str) and e.startswith(APM_PREFIX))]
    ai_entries = sorted(f"{APM_PREFIX}{p}" for p in compatible)

    # Rebuild: non-ai-helpers entries first, then the ai-helpers block.
    # If there were previously no ai-helpers entries at all, append at end.
    new_deps = non_ai + ai_entries
    return new_deps, added, removed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    here = os.path.dirname(os.path.abspath(__file__))
    default_apm = os.path.join(here, "apm.yml")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("apm_yml", nargs="?", default=default_apm, help="Path to apm.yml")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Fetching plugin list from {REPO}...")
    all_plugins = list_plugin_dirs(args.token)
    print(f"Found {len(all_plugins)} plugins upstream.")

    compatible: set[str] = set()
    skipped: list[str] = []

    for plugin in all_plugins:
        plugin_json = fetch_plugin_json(plugin, args.token)
        if plugin_json is not None and has_incompatible_deps(plugin_json):
            bad_deps = [
                d["name"]
                for d in plugin_json.get("dependencies", [])
                if isinstance(d, dict) and "name" in d and "git" not in d
            ]
            print(
                f"  skip  {plugin}  "
                f"(incompatible deps: {', '.join(bad_deps)})"
            )
            skipped.append(plugin)
        else:
            compatible.add(plugin)

    print(f"\n{len(compatible)} compatible, {len(skipped)} skipped.")

    data = load_apm_yml(args.apm_yml)
    deps: list = data.setdefault("dependencies", {}).setdefault("apm", [])

    new_deps, added, removed = update_deps(deps, compatible)

    if not added and not removed:
        print("\napm.yml is already up to date.")
        return

    if added:
        print(f"\nPlugins to add ({len(added)}):")
        for p in added:
            print(f"  + {APM_PREFIX}{p}")
    if removed:
        print(f"\nPlugins to remove ({len(removed)}):")
        for p in removed:
            print(f"  - {APM_PREFIX}{p}")

    if args.dry_run:
        print("\n--dry-run: no changes written.")
        return

    data["dependencies"]["apm"] = new_deps
    save_apm_yml(args.apm_yml, data)
    print(f"\napm.yml updated ({args.apm_yml}).")


if __name__ == "__main__":
    main()
