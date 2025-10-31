FROM debian:bullseye-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    perl \
    build-essential \
    libcurses-perl \
    python3 \
    python3-pip \
    telnet \
    netcat \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install requests

# Create sysop user
RUN useradd -m -s /bin/bash sysop

# Switch to sysop user
USER sysop
WORKDIR /home/sysop

# Clone and install DXSpider
RUN git clone git://scm.dxcluster.org/scm/spider && \
    cd spider && \
    perl Makefile.PL && \
    make

# Copy application files
COPY --chown=sysop:sysop config/dxvars.pm /home/sysop/spider/local/DXVars.pm
COPY --chown=sysop:sysop scripts/pota_bridge.py /home/sysop/pota_bridge.py
COPY --chown=sysop:sysop scripts/start.sh /home/sysop/start.sh

RUN chmod +x /home/sysop/start.sh /home/sysop/pota_bridge.py

# Expose cluster port
EXPOSE 7300

# Health check script
USER root
RUN echo '#!/bin/bash\nnetstat -an | grep -q ":7300.*LISTEN"' > /usr/local/bin/health_check.sh && \
    chmod +x /usr/local/bin/health_check.sh

USER sysop

CMD ["/home/sysop/start.sh"]