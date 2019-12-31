#! /usr/bin/bash
#
# Example:
# ./manual-opt.sh $(git rev-parse --show-toplevel)/llvm/projects/test-suite/SingleSource/UnitTests/Integer/global.c manual-opt-O3.txt

set -e

function usage {
  echo "usage: manual-opt.sh <source file> <args...>"
  echo ""
  echo "Compares three sequences optimizer calls on the same program:"
  echo "1: opt -O3"
  echo "2: opt <closure.txt>"
  echo "3: opt <closure-1.txt> | opt <closure-2.txt> (best approx, maybe)"
  echo ""
  echo "Intermediate files are stored in the manual-opt/ directory."
  echo ""
  echo "source:  Source file (.c, .bc)."
  echo "args:    Additional compile args"
}

function log {
  echo -en '\n\x1b[35m<> '
  echo -n "$@"
  echo -e '\x1b[0m'
}

function execute {
  echo '   % '"$@"
  "$@"
}

# Check that there are enough arguments
if [[ -z "$1" ]]; then
  usage
  exit 1
fi

if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
  usage
  exit 0
fi

# Options

name=$(basename ${1%.*})
pref=manual-opt/$name

src=$1
shift

# Make a folder for all temporary files
mkdir -p manual-opt

# Build intermediate representation
if [[ $src == *.c ]]; then
  log "Compiling with clang:"
  execute clang -O0 -S -emit-llvm $src -o $pref.ll "$@"
elif [[ $src == *.bc ]]; then
  log "Compiling with llvm-dis:"
  execute llvm-dis $src -o $pref.ll
else
  echo "error: I don't know how to compile this file :'(" >&2
fi

# Optimize with two different sets of options

log "Optimizing with opt -O3:"
execute opt -S -mtriple=' ' -O3 $pref.ll -o $pref.1.ll

log "Optimizing with closure.txt:"
execute opt -S -mtriple=' ' $(cat closure-{1,2}.txt) $pref.ll -o $pref.2.ll

log "Optimizing with a custom sequence:"
execute opt -S $(cat closure-1.txt) $pref.ll -o $pref.3,0.ll
execute opt -S $(cat closure-2.txt) $pref.3,0.ll -o $pref.3.ll

# Compile to assembler code

# log "Compiling IR to object files:"
execute clang -O0 -c $pref.1.ll -o $pref.1.o
execute clang -O0 -c $pref.2.ll -o $pref.2.o
execute clang -O0 -c $pref.3.ll -o $pref.3.o

# Compile to machine code

log "Assembling to machine code:"
execute clang -O0 $pref.1.o -o $pref.1 -lm
execute clang -O0 $pref.2.o -o $pref.2 -lm
execute clang -O0 $pref.3.o -o $pref.3 -lm

log "Comparing output files:"
execute diff $pref.1.ll $pref.2.ll > /dev/null || true

if ! diff $pref.1.ll $pref.2.ll > /dev/null 2>&1; then
  echo -e "\nIR code of methods 1 and 2 differs. :-("
else
  echo -e "\nIR code of methods 1 and 2 is the same. :-)"
fi

log "Comparing manual optimization sequences:"
execute diff $pref.1.ll $pref.3.ll > /dev/null || true

if ! diff $pref.1.ll $pref.3.ll > /dev/null 2>&1; then
  echo -e "\nIR code of methods 1 and 3 differs. :-("
else
  echo -e "\nIR code of methods 1 and 3 is the same. :-)"
fi

log "Comparing program speed:"
execute perf stat -r 100 -o /tmp/perf.1 ./$pref.1 >/dev/null 2>&1
execute perf stat -r 100 -o /tmp/perf.2 ./$pref.2 >/dev/null 2>&1
execute perf stat -r 100 -o /tmp/perf.3 ./$pref.3 >/dev/null 2>&1

cat /tmp/perf.{1,2,3}

exit 0
