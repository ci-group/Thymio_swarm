#!/bin/sh
sleep 5
if ps aux | grep "[a]sebamedulla" > /dev/null
then
    echo "asebamedulla is already running"
else
    (asebamedulla "ser:device=/dev/ttyACM0" &)
    python /home/pi/rpis/algorithm.py
fi

