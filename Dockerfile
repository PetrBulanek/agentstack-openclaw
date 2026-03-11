FROM python:3.13-bookworm

# Install Node.js 22 and git
RUN apt-get update && \
    apt-get install -y curl git && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install OpenClaw globally
RUN npm install -g openclaw@latest

# Install uv
RUN pip install uv

# Pre-configure OpenClaw home directory
RUN mkdir -p /root/.openclaw

WORKDIR /app

# Copy agent source and install Python dependencies from PyPI
COPY pyproject.toml ./
COPY src/ ./src/
RUN uv sync --no-dev

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
