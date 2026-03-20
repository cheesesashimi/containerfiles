#!/usr/bin/env python3

import subprocess
import yaml


def run_command(command):
    """Helper to run shell commands and print output."""
    print(f"Executing: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing {command}: {e}")


# Load the YAML file
with open("plugins.yaml", "r") as file:
    data = yaml.safe_load(file)

# Iterate through the marketplaces
for entry in data.get("claude_plugins", []):
    marketplace = entry.get("marketplace")
    plugins = entry.get("plugins", [])

    if marketplace:
        # 1. Add the marketplace
        run_command(
            [
                "/home/claude/.local/bin/claude",
                "plugin",
                "marketplace",
                "add",
                marketplace,
            ]
        )

        # 2. Install each plugin
        for plugin in plugins:
            run_command(["/home/claude/.local/bin/claude", "plugin", "install", plugin])

print("\nPlugin installation process complete.")
