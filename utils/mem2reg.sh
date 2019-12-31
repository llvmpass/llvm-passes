#! /bin/bash

set -e
. $(dirname $0)/toolbox.sh

box_compile
box_opt -mem2reg
box_asm