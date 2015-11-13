15:19#!/bin/bash
while read line
do
	echo "COPY files TO $line"
	scp algorithm/algorithmForaging.py  pi@"$line":/home/pi/algorithmForaging.py
	scp algorithm/parameters.py  pi@"$line":/home/pi/parameters.py
	scp algorithm/ThymioController.py pi@"$line":/home/pi/ThymioController.py
	scp algorithm/Simulation.py pi@"$line":/home/pi/Simulation.py
	scp algorithm/Inbox.py pi@"$line":/home/pi/Inbox.py
	scp algorithm/ConfigParser.py pi@"$line":/home/pi/ConfigParser.py
	scp algorithm/ConnectionsListener.py pi@"$line":/home/pi/ConnectionsListener.py
	scp algorithm/MessageSender.py pi@"$line":/home/pi/MessageSender.py
	scp algorithm/Helpers.py pi@"$line":/home/pi/Helpers.py
	scp algorithm/MessageReceiver.py pi@"$line":/home/pi/MessageReceiver.py
	scp algorithm/CommandsListener.py pi@"$line":/home/pi/CommandsListener.py
	scp algorithm/CameraVision.py pi@"$line":/home/pi/CameraVision.py
	scp algorithm/classes.py pi@"$line":/home/pi/classes.py
	scp algorithm/asebaCommands.aesl pi@"$line":/home/pi/asebaCommands.aesl
	scp config.json pi@"$line":/home/pi/config.json
	echo -e "\r"
done <./bots.txt
wait
