#! /bin/sh

export PRODUCTION=1
logger "Starting dryer GUI"
while [ 1 ] ; do
    python3 /home/pi/dryer/gui.py 2>&1 | logger
    sleep 5
    logger "Restarting dryer GUI"
done
