FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 1. 安装依赖并创建用户
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    gnupg \
    apache2-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash nexus

# 2. 安装 ngrok
RUN curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /usr/local/bin/ngrok.asc > /dev/null \
    && curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | gpg --dearmor > /usr/local/bin/ngrok.asc \
    && curl -sL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar -xz -C /usr/local/bin \
    && chmod +x /usr/local/bin/ngrok \
    && rm -f /usr/local/bin/ngrok.asc

# 3. --- 修复 Nginx 系统目录权限 ---
# 必须先强制创建这些目录，防止 slim 镜像中缺失，然后再移交权限
RUN mkdir -p /etc/nginx /var/log/nginx /var/lib/nginx /var/cache/nginx /run && \
    chown -R nexus:nexus /etc/nginx /var/log/nginx /var/lib/nginx /var/cache/nginx /run && \
    touch /run/nginx.pid && chown nexus:nexus /run/nginx.pid

# 4. 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制代码
COPY --chown=nexus:nexus . .

# 6. --- 关键修改：修复 Nginx 日志文件权限 ---
# 预先创建报错的日志文件，并给满权限，防止宿主机 volume 挂载导致权限冲突
RUN mkdir -p /app/data /app/logs && \
    touch /app/logs/nginx_access.log /app/logs/nginx_error.log && \
    chown -R nexus:nexus /app/data /app/logs && \
    chmod -R 777 /app/logs

# 7. 确保脚本有执行权限 (在切换用户前执行)
RUN chmod +x startup.sh

# 8. 切换用户
USER nexus

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["bash", "startup.sh"]
