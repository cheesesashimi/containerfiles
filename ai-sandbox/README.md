# ai-sandbox

This image is primarily intended to be used by CLI-based AI tools such as Claude Code CLI, OpenCode, etc. The intent behind them is to provide a fully-featured yet sandboxed work environment to run these tools in. This provides the following benefits:

- Keeps these tools relatively confined and prevents more destructive actions such as erasing ones disk or work.
- Workspace is non-persistent by nature. It can be instantly recreated should any destructive actions occur.
- Reduces the likelihood of credential leakage since the only credentials that are inside the container are the ones that you mount.

While this image provides some protection against a misbehaving agent, it is not foolproof. Container breakouts are still very possible. Treat this image as you would any other container image and understand the security implications.

## Image pulls

This image may be pulled from `quay.io/zzlotnik/toolbox:ai-helpers-fedora-44` using the container runtime of your choosing.

## Using the image

My typical use-case for this image includes using nested Podman from within. Consequently, I have to start the image with more elevated permissions than I would reasonably like to. However, your use-case may be that this is not required. To start the image, I use [this script](https://github.com/cheesesashimi/oc-oneliners/blob/main/enter-ai-sandbox.sh) which also creates a tmux session within the container so that one can detach and reattach easily. Feel free to use and modify this script for your use-case.
