# Utilities for performance measurement

Not much right now. The `gnuplot-speedup.py` script is used to convert
performance counter statistics from `perf` to a space-separated data file
intended for Gnuplot. This is because `perf` outputs `.perfstats` files with a
pretty hard-to-parse format. The command-line describes the precise output.

This is useful to obtain execution time statistics for an LLVM test suite which
has been ran through `perf` rather than LLVM's integrated tester.
