#! /usr/bin/bash

set -e

log() {
  echo -n '<> '
  echo "$@"
}
execute() {
  echo '  % '"$@" >&2
  "$@"
}

# Options

P1="$2"
P2="$3"

name=$(basename ${1%.*})
pref=commut/$name

# Make a folder for all temporary files
mkdir -p commut

# Build intermediate representation
if [[ $1 == *.c ]]; then
  log "Compiling with clang:"
  execute clang -O0 -c -emit-llvm $1 -o $pref.bc
elif [[ $1 == *.cpp ]]; then
  log "Compilang with clang++:"
  execute clang++ -O0 -c -emit-llvm $1 -o $pref.bc
elif [[ $1 == *.bc ]]; then
  log "Copying bitcode file:"
  execute cp $1 $pref.bc
else
  echo "error: I don't know how to compile this file :'(" >&2
fi

# Optimize with two different sets of options

log "Optimizing with $P1 then $P2:"
execute opt $P1 $P2 $pref.bc -o $pref.12.bc

log "Optimizing with $P2 then $P1:"
execute opt $P2 $P1 $pref.bc -o $pref.21.bc

# Compile to machine code

log "Assembling to machine code:"
execute clang++ -O0 $pref.12.bc -o $pref.12
execute clang++ -O0 $pref.21.bc -o $pref.21

# Comparing performance
log "Comparing performance:"
execute perf stat --null -r 10 $pref.12 2>&1 | tee $pref.12.stats
execute perf stat --null -r 10 $pref.21 2>&1 | tee $pref.21.stats

