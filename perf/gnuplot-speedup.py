#! /usr/bin/env python3

import sys
import re
import os
import glob
import statistics

help_message = f"""
usage: {sys.argv[0]} <ref folder> <data folder>

Analyzes perfstats files produced by running perf in a testsuite directory
created by the configure-perf.py script in /testsuite. Computes the speedup of
executables in the data folder as compared with the reference folder.

Outputs a space-separated data file, intended for Gnuplot, with five fields:
* Test name
* sp_time_avg: average speedup in terms of execution time
* sp_time_dev: standard deviation of this speedup
* sp_ins_avg:  average speedup in terms of executed instructions
* ins_devn:    standard deviation of number of instructions (see below)

The second standard deviation is not the standard deviation of the speedup in
terms of executed instruction count, because this value can only be calculated
if all measures of instruction counts are available, and [perf] does not
provide them. Instead it is the standard deviation of the mesures in the data
folder, expressed as a propotion of sp_ins_avg.
""".strip()

if len(sys.argv) < 3:
    print(help_message)
    sys.exit(0)

re_avg = r'^ *(\S+) \+- (\S+) seconds time elapsed'
re_avg = re.compile(re_avg, re.MULTILINE)

re_ins = r'^ *([0-9,]+) *instructions:u.*\( \+- *([0-9.]+)% \)'
re_ins = re.compile(re_ins, re.MULTILINE)

re_table = r'Table of individual measurements:\n(.+\n)+'
re_table = re.compile(re_table)

re_meas = r' [0-9.]+ '
re_meas = re.compile(re_meas)

ref_files  = glob.glob(os.path.join(sys.argv[1], '*.perfstats'))
data_files = glob.glob(os.path.join(sys.argv[2], '*.perfstats'))

info = dict()

class NoDataFound(Exception):
    pass

def getstats(file):
    basename = os.path.basename(file[:-10])
    data = open(file, 'r').read()

    mavg = re.search(re_avg, data)
    if mavg is None:
        print(f"[{basename}] ERROR: no match found", file=sys.stderr)
        raise NoDataFound()

    mins = re.search(re_ins, data)
    if mins is None:
        print(f"[{basename}] ERROR: no insn match found", file=sys.stderr)
        raise NoDataFound()

    ins_avg  = int(mins[1].replace(",", ""))
    ins_devn = float(mins[2]) / 100

    mtable = re.search(re_table, data)
    if mtable is None:
        print(f"[{basename}] ERROR: no table found", file=sys.stderr)
        raise NoDataFound()

    table = mtable[0]
    measures = [ float(m.strip()) for m in re.findall(re_meas, table) ]

    return basename, {
      'time':      measures,
      'ins_avg':   ins_avg,
      'ins_devn':  ins_devn,
    }

for file in data_files:
    try:
        name, stats = getstats(file)
        info[name] = stats
    except NoDataFound:
        pass

for file in ref_files:
    try:
        name, ref = getstats(file)
    except NoDataFound:
        continue

    if name not in info:
        continue
    inf = info[name]

    inf['ref_time']     = ref['time']
    inf['ref_ins_avg']  = ref['ins_avg']
    inf['ref_ins_devn'] = ref['ins_devn']

    speedup = [ y/x for x, y in zip(inf['time'], ref['time']) if x > 0 ]

    inf['sp_time']     = speedup
    inf['sp_time_avg'] = statistics.mean(speedup)
    inf['sp_time_dev'] = statistics.stdev(speedup)

    inf['sp_ins_avg'] = ref['ins_avg'] / inf['ins_avg']

info = { name: data for name, data in info.items()
         if 'ref_time' in data }

fields = "sp_time_avg sp_time_dev sp_ins_avg ins_devn".split()
print(f"# {' '.join(fields)}")

for name, inf in info.items():
    print(name, end='')
    for f in fields:
        print(f" {inf.get(f)}", end='')
    print("")
