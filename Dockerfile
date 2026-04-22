FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    apache2-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash nexus

# Install ngrok
RUN curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /usr/local/bin/ngrok.asc > /dev/null \
    && curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | gpg --dearmor > /usr/local/bin/ngrok.asc \
    && curl -sL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar -xz -C /usr/local/bin \
    && chmod +x /usr/local/bin/ngrok \
    && rm -f /usr/local/bin/ngrok.asc

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=nexus:nexus . .

# Data directories (created after user switch)
RUN mkdir -p /app/data /app/logs && chown nexus:nexus /app/data /app/logs

# Switch to non-root user
USER nexus

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["bash", "startup.sh"]
