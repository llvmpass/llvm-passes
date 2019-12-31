#! /bin/bash

if [[ "$1" == "--testsuite" ]]; then

  in=$2
  out=$3
  DEFINES=$4
  INCLUDES=$5
  FLAGS=$6
  DEP_FILE=$7
  MD=$8
  CLANG=$9
  OPT=$(dirname "$CLANG")/opt
  LLC=$(dirname "$CLANG")/llc

  o0="-O0 -Xclang -disable-O0-optnone"

  # Compile the source to bitcode.
  # Does not produce dependency information if $1 is specified.
  #   $1: Output file name (optional, defaults to "$out.bc")
  box_compile() {
    output=${1:-$out.bc}
    [[ -z $1 ]] && deps="$MD -MT $out -MF $DEP_FILE"

    $CLANG -emit-llvm $DEFINES $INCLUDES $FLAGS $deps -o $output -c $in $o0
  }

  # Compile the source to text code.
  #   $1: Output file name (required)
  box_compile_ll() {
    $CLANG -S -emit-llvm $DEFINES $INCLUDES $FLAGS $deps -o $1 -c $in $o0
  }

  # Optimize the bitcode file in-place
  #   $@: Arguments to opt, excluding source and target file
  box_opt() {
    $OPT "$@" $out.bc -o $out.bc
  }

  # Assemble bitcode to the output file
  # Always assembles "$out.bc" to "$out".
  box_asm() {
    $CLANG -c $out.bc -o $out $FLAGS -O0
  }

else

  in=$1
  out=${2:-$1.out}

  box_compile() {
    true
  }

  box_compile_ll() {
    true
  }

  box_opt() {
    $OPT "$@" $in -o $out
  }

  box_asm() {
    true
  }

fi
