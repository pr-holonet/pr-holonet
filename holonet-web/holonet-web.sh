#!/bin/bash

set -euo pipefail


readlink_f()
{
    if [ $(uname) = 'Darwin' ]
    then
        local f=$(readlink "$1")
        if [[ $f == '' ]]
        then
            f="$1"
        fi
        local d=$(dirname "$f")
        local b=$(basename "$f")
        (cd "$d" && echo "$(pwd -P)/$b")
    else
        readlink -f "$1"
    fi
}


thisdir=$(dirname $(readlink_f "$0"))

if [ -d "$thisdir/../../.pyenv3"* ]
then
    env=$(ls "$thisdir/../../.pyenv3"* | head -1)
    . "$env/bin/activate"
fi
cd "$thisdir"
exec python3 app.py
