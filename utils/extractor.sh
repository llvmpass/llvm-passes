#! /usr/bin/bash

# Customize this, obviously
OUT_DIRECTORY="$HOME/Projects/llvm-ir"

set -e
. $(dirname $0)/tools/ts.sh

box_compile

copy="$OUT_DIRECTORY/$out.bc"
mkdir -p $(dirname "$copy")
cp $out.bc $copy

box_asm
