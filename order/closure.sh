#! /usr/bin/bash

set -e

OPT='opt -debug-pass=Arguments -disable-verify -disable-output'
REF='-O3'
P1="$(cat closure-1.txt)"
P2="$(cat closure-2.txt)"

auto() {
  echo | $OPT $REF 2>&1
}

manual() {
  echo | $OPT $P1 2>&1
  echo | $OPT $P2 2>&1
}

clean() {
  sed 's/^Pass Arguments:  //' \
  | tr ' ' '\n'
}

echo -e "\n<> Output from opt $REF:"
auto

echo -e "\n<> Output from the manual sequence:"
manual

echo -e "\n<> Diff between the sequences:"
diff -u0 <(auto | clean) <(manual | clean) || true

if [[ -z "$1" ]]; then
  echo ""
  echo "If you provide a file as argument, I will compare $REF with the custom"
  echo "sequence and make a text IR diff."
  exit 0
fi

echo -e "\n<> Diff between optimized files:"
diff <(opt -S $REF $1) <(opt -S $P1 $1 | opt -S $P2)

