#!/bin/bash

# Copyright 2017 Hadi Esiely
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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
    env=$(ls -d "$thisdir/../../.pyenv3"* | head -1)
    export VIRTUAL_ENV_DISABLE_PROMPT=1
    . "$env/bin/activate"
fi
cd "$thisdir"
exec python3 app.py
