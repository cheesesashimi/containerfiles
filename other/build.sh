#!/usr/bin/env bash

for containerfile in Containerfile*; do
  tag="${containerfile/Containerfile./}"
  podman build -t "localhost/$tag:latest" --file="$containerfile" .
done
