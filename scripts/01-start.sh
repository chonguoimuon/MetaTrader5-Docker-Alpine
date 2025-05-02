#!/bin/bash

# Source common variables and functions
source /scripts/02-common.sh

# Run installation scripts
/scripts/03-install-mono.sh
/scripts/04-install-mt5.sh
/scripts/05-install-python.sh
/scripts/06-install-libraries.sh

# Start servers
/scripts/07-start-wine-flask.sh

#Start MT5
/scripts/08-start-wine-mt5.sh

# Keep the script running
tail -f /dev/null