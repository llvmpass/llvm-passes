#! /bin/bash

set -e
. $(dirname $0)/toolbox.sh

box_compile
box_opt -licm -loop-unswitch
box_asm
