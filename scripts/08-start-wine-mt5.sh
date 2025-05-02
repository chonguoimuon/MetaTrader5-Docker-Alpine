#!/bin/bash

source /scripts/02-common.sh

log_message "RUNNING" "08-start-wine-mt5.sh"

# Recheck if MetaTrader 5 is installed
if [ -e "$mt5file" ]; then
    log_message "INFO" "File $mt5file is installed. Running MT5..."
    $wine_executable "$mt5file" &
else
    log_message "ERROR" "File $mt5file is not installed. MT5 cannot be run."
fi