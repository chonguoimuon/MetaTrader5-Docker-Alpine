# Stage 1: Base image with APK packages
FROM ghcr.io/linuxserver/baseimage-kasmvnc:alpine321 AS base

# set version label
ARG BUILD_DATE
ARG VERSION
LABEL build_version="Metatrader5 Docker:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="github@gmartin.net"

# title
ENV TITLE=Metatrader5

ENV WINEPREFIX="/config/.wine"

#install wine and dependencies
RUN apk update && apk add wine \
    dos2unix \
    wget \
    && rm -rf /apk /tmp/* /var/cache/apk/*

# Stage 2: Final image
FROM base

# add local files
COPY app /app
COPY scripts /scripts
RUN dos2unix /scripts/*.sh && \
    chmod +x /scripts/*.sh && \
    chmod +x /app/*

COPY /root /

RUN touch /var/log/mt5_setup.log && \
    chown abc:abc /var/log/mt5_setup.log && \
    chmod 644 /var/log/mt5_setup.log
    
# remove sudo
#RUN apk del sudo

# ports and volumes
EXPOSE 3000 5001

VOLUME /config
    