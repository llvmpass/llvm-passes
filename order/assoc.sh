#! /usr/bin/bash

set -e

execute() {
  echo '  % '"$@" >&2
  "$@"
}

n=assoc/stress
# opt='opt -mtriple=x86_64-unknown-linux-gnu -preserve-ll-uselistorder -preserve-bc-uselistorder'
opt='opt'

p="$(cat closure-1.txt)"
q="$(cat closure-2.txt)"

mkdir -p assoc

# Create a random file if no input is specified
if [[ -z $1 ]]; then
  execute llvm-stress -size=10000 > $n.ll
else
  execute cp $1 $n.ll
fi

# Dry run
execute $opt    $n.ll -o $n.bc
execute $opt -S $n.ll -o $n.ll.1

# Build -p -q
execute $opt $p $q $n.bc  -o $n-12.bc
execute clang -c $n-12.bc -o $n-12.o

# Build -p | -q
execute $opt $p $n.bc      -o $n-1.bc
execute $opt $q $n-1.bc    -o $n-1-2.bc
execute clang -c $n-1-2.bc -o $n-1-2.o

# Disassemble and reassemble results
execute llvm-dis $n-12.bc    -o $n-12.ll.2
execute llvm-dis $n-1-2.bc   -o $n-1-2.ll.2
execute llvm-as  $n-12.ll.2  -o $n-12.bc.2
execute llvm-as  $n-1-2.ll.2 -o $n-1-2.bc.2

# Check when staying in text form
execute $opt -S $p $q $n.ll.1   -o $n-12.ll.1
execute $opt -S $p    $n.ll.1   -o $n-1.ll.1
execute $opt -S $q    $n-1.ll.1 -o $n-1-2.ll.1
