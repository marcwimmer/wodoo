#!/bin/bash
echo
echo 1. Create a new bot and get the Token
read -r -p "Now enter the token [$TELEGRAMBOTTOKEN]:" token
if [[ -z "$token" ]]; then
	token=$TELEGRAMBOTTOKEN
fi
if [[ -z "$token" ]]; then

	exit 0
fi
echo 2. Create a new public channel, add the bot as administrator and users
read -r -p "Now enter the channel name with @:" channelname
if [[ -z "$channelname" ]]; then
	exit 0
fi

python "/send.py" "__setup__" "$token" "$channelname"
echo "Finished - chat id is stored; bot can send to channel all the time now."
