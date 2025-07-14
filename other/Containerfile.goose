# Used for working with goose (https://block.github.io/goose/) so that it can run containerized
FROM quay.io/zzlotnik/toolbox:kube-fedora-42
RUN --mount=type=cache,target=/var/cache/dnf,z \
    dnf install -y libxcb && \
    curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | bash && \
    mv /root/.local/bin/goose /usr/local/bin/goose
