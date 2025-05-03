#!/bin/bash

source /scripts/02-common.sh

log_message "RUNNING" "06-install-libraries.sh"

# Install MetaTrader5 library in Windows if not installed
log_message "INFO" "Installing MetaTrader5 library and dependencies in Windows"
if ! is_wine_python_package_installed "MetaTrader5"; then
	$wine_executable python -m ensurepip --upgrade & 
	#$wine_executable python -m pip install --upgrade pip & 
    $wine_executable python -m pip install --no-cache-dir -r /app/requirements.txt
fi

# Install Gecko if not present
if [ ! -e "/config/.wine/drive_c/windows/system32/gecko/plugin" ]; then
    log_message "INFO" "Downloading and installing Gecko..."
    wget -O /tmp/Gecko.msi https://dl.winehq.org/wine/wine-gecko/2.47.4/wine-gecko-2.47.4-x86_64.msi > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        WINEDLLOVERRIDES=mscoree=d wine msiexec /i /tmp/Gecko.msi /qn
        if [ $? -eq 0 ]; then
            log_message "INFO" "Gecko installed successfully."
        else
            log_message "ERROR" "Failed to install Gecko."
        fi
        rm -f /tmp/Gecko.msi
    else
        log_message "ERROR" "Failed to download Gecko installer."
    fi
else
    log_message "INFO" "Gecko is already installed."
fi