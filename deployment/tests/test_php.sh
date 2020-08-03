#!/usr/bin/env bash

RED='\033[0;31m' # red color
NC='\033[0m'     # no color
BOLD=$(tput bold)
NORMAL=$(tput sgr0)


which_php=$(which php)

if [[ $which_php == *"/php"* ]]; then
    echo "php found"
else
    echo "${BOLD}could not find 'php' in 'which php' output!!!"
    echo -e "${RED}TEST FAILED${NC}"
    exit 1
fi
