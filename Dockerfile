#FROM debian:bullseye-slim
FROM --platform=linux/amd64 debian:bullseye-slim
# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    perl \
    build-essential \
    libcurses-perl \
    libtimedate-perl \
    libdigest-sha-perl \
    python3 \
    python3-pip \
    telnet \
    netcat \
    procps \
    wget \
    socat \
    libnet-cidr-lite-perl \
    && rm -rf /var/lib/apt/lists/*

    # Install Python dependencies
RUN pip3 install requests

# Create sysop user
RUN useradd -m -s /bin/bash sysop

# Switch to sysop user
USER root
WORKDIR /home/sysop

# Download 
RUN wget http://www.dxcluster.org/download/spider-1.55.tar.gz && \
    tar -xzf spider-1.55.tar.gz && \
    rm spider-1.55.tar.gz && \
    chown -R sysop:sysop spider && \
    ln -s /home/sysop/spider /spider

USER sysop

# Copy application files
# Copy application files
COPY --chown=sysop:sysop scripts/pota_bridge.py /home/sysop/pota_bridge.py
COPY --chown=sysop:sysop scripts/telnet_server.py /home/sysop/telnet_server.py
COPY --chown=sysop:sysop scripts/start.sh /home/sysop/start.sh

RUN chmod +x /home/sysop/start.sh /home/sysop/pota_bridge.py /home/sysop/telnet_server.py
RUN chmod +x /home/sysop/start.sh /home/sysop/pota_bridge.py

# Expose cluster port
EXPOSE 7300

# Health check script
USER root
RUN echo '#!/bin/bash\nnetstat -an | grep -q ":7300.*LISTEN"' > /usr/local/bin/health_check.sh && \
    chmod +x /usr/local/bin/health_check.sh

USER sysop

CMD ["/home/sysop/start.sh"]