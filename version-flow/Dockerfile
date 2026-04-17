FROM amazon/aws-cli:2.8.12 AS awscli
FROM python:3.14.0-bookworm

# copy the prebuild aws-cli from the aws-cli image
COPY --from=awscli /usr/local/bin /usr/local/bin
COPY --from=awscli /usr/local/aws-cli /usr/local/aws-cli

SHELL ["/bin/bash", "-c"]

RUN pip install --upgrade pip setuptools wheel \
  && pip install pipx \
  && pipx install "poetry==2.0.1"

# Ensure that apps installed by pipx (i.e. poetry) are findable,
# but that poetry installs the app dependencies globally
ENV PATH="/root/.local/bin:$PATH"
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_HTTP_BASIC_CLAIRITY_USERNAME=aws

# It is OK to have this written to docker history because it is
# a read-only temporary token.
ARG CODEARTIFACT_AUTH_TOKEN
ENV POETRY_HTTP_BASIC_CLAIRITY_PASSWORD=$CODEARTIFACT_AUTH_TOKEN

RUN mkdir -p /home/app/version-flow
WORKDIR /home/app/version-flow

# One layer installing package dependencies
COPY pyproject.toml *.lock ./
RUN poetry install --no-root --no-ansi --no-interaction

# Separate layer installing the local Python package
COPY version_flow version_flow
COPY README.md README.md
RUN poetry install --no-ansi --no-interaction