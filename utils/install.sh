#! /bin/bash
# This script should work smoothly in the general case but is not trustworthy
# enough to use blindly, I guess. If the script is stopped midway the
# restarting it will resume the build automatically.

set -e

# LLVM version.
version=8.0.0

# Build flags.
# * -G Ninja instructs CMake to target the Ninja backend; this is the normal
#   backend for LLVM developers, and also useful for resuming the build.
# * LLVM_PARALLEL_LINK_JOBS=1 asks for serial link jobs, which avoids atrocious
#   RAM usage (> 10 GB) at link time
# * BUILD_SHARED_LIBS=ON speeds up link on re-compilations
# * CMAKE_BUILD_TYPE=MinSizeRel will build a minimum-size fast release version
#   of LLVM instead of the debug version with asserts.
flags_llvm="-G Ninja -D LLVM_PARALLEL_LINK_JOBS=1 -D BUILD_SHARED_LIBS=ON \
            -D CMAKE_BUILD_TYPE=MinSizeRel"

# Download LLVM, Clang, Clang extra tools and the LLVM test suite

base="https://releases.llvm.org/$version"
wget -m -nv "$base/llvm-$version.src.tar.xz"
wget -m -nv "$base/cfe-$version.src.tar.xz"
wget -m -nv "$base/clang-tools-extra-$version.src.tar.xz"
wget -m -nv "$base/compiler-rt-$version.src.tar.xz"
wget -m -nv "$base/test-suite-$version.src.tar.xz"

# Extract source code (only newer files)

extract() {
  src="releases.llvm.org/$version/$1-$version.src.tar.xz"
  dst="$2"

  # Only extract if the archive is newer than the directory
  if [[ ! -e $dst ]]; then
    mkdir -p $dst
  elif [[ ! $src -nt $dst ]]; then
    echo "Skipping already-extracted $src"
    return
  fi

  echo "Extracting $src into $dst"
  tar -xJf $src -C $dst --strip-components=1
}

# Extract the source archives

extract "llvm"              llvm/
extract "cfe"               llvm/tools/clang/
extract "clang-tools-extra" llvm/tools/clang/tools/extra/
extract "compiler-rt"       llvm/projects/compiler-rt/
extract "test-suite"        llvm/projects/test-suite/

# Configure or reconfigure the build (Ninja will not recompile everything if
# the build is reconfigured with the same options)

mkdir -p build && cd build
cmake $flags_llvm ../llvm

# Build and roll!
ninja
