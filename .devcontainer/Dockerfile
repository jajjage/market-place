FROM mcr.microsoft.com/devcontainers/python:1-3.13-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/home/vscode/.local" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Update PATH to include Poetry
ENV PATH="${POETRY_HOME}/bin:$PATH"

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
        redis-tools \
        supervisor \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry - run as root to ensure permissions
RUN curl -sSL https://install.python-poetry.org | python3 -

USER root
RUN mkdir -p /workspaces \
 && chown -R vscode:vscode /workspaces


# Change ownership of Poetry installation to vscode user
RUN chown -R vscode:vscode ${POETRY_HOME}


# Switch to the vscode user for subsequent commands
USER vscode
WORKDIR /workspaces

# Poetry is now available in PATH, so no need to use the full path
RUN poetry config virtualenvs.in-project true