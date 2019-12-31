#! /bin/bash

set -e
. $(dirname $0)/toolbox.sh

box_compile
box_opt -simplifycfg
box_asm