# ai-sandbox

These images are primarily intended to be used by CLI-based AI tools such as Claude Code CLI, Gemini CLI, etc. The intent behind them is to provide a fully-featured yet sandboxed work environment to run these tools in. This provides the following benefits:

- Keeps these tools relatively confined and prevents more destructive actions such as erasing ones disk or work.
- Workspace can be instantly recreated should any destructive actions occur.
- Reduces the likelihood of credential leakage since the only credentials that are inside the container are the ones that you mount.

While these images provide some protection against a misbehaving agentic AI, they are not foolproof. Treat these images as you would any other container image.
