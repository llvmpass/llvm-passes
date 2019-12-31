#! /bin/bash

set -e
. $(dirname $0)/toolbox.sh

box_compile
box_opt -instcombine
box_asm