FROM docker.m.daocloud.io/library/debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/runtime-app \
    OPTIMIZER_HOST=0.0.0.0 OPTIMIZER_PORT=18080 \
    OPTIMIZER_API_KEY_FILE=/run/secrets/wenxinyiyan-api-key
RUN sed -i 's|http://deb.debian.org/debian-security|http://mirrors.ustc.edu.cn/debian-security|g; s|http://deb.debian.org/debian|http://mirrors.ustc.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources \
    && printf 'Acquire::http::Timeout "30";\nAcquire::Retries "1";\n' > /etc/apt/apt.conf.d/80-download-timeout \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ca-certificates curl xvfb x11vnc novnc websockify \
    openbox supervisor dbus-x11 xdg-utils chromium fonts-wqy-zenhei \
    libgtk-3-0 libnotify4 libnss3 libxss1 libxtst6 libatspi2.0-0 libuuid1 \
    libsecret-1-0 libasound2 libgbm1 libxshmfence1 libdrm2 procps \
    && rm -rf /var/lib/apt/lists/*
COPY deployment/downloads/WorkBuddy.deb /tmp/WorkBuddy.deb
RUN echo '12149ad8c0cd748fd5062d8f62c7827d688d8095427ada99b1ae9e7019897523  /tmp/WorkBuddy.deb' | sha256sum -c - \
    && dpkg -i /tmp/WorkBuddy.deb && rm /tmp/WorkBuddy.deb \
    && useradd --uid 1000 --create-home --shell /bin/bash app
WORKDIR /app
COPY requirements.lock.txt ./requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir \
    --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt
COPY workbuddy_optimizer.py workbuddy_transport.py optimizer_service.py ./
COPY config/request-template.json ./config/request-template.json
COPY deployment/supervisord.conf /etc/supervisor/conf.d/wenxinyiyan.conf
COPY deployment/entrypoint.sh /usr/local/bin/wenxinyiyan-entrypoint
COPY deployment/chromium-container /etc/chromium.d/wenxinyiyan-container
RUN chmod 755 /usr/local/bin/wenxinyiyan-entrypoint
EXPOSE 18080 6080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD curl -fsS http://127.0.0.1:18080/health || exit 1
ENTRYPOINT ["/usr/local/bin/wenxinyiyan-entrypoint"]
