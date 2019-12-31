#! /usr/bin/env python3
import re
import sys


def main():
    times = {
        'exit': 0,
        'real': 0.0,
        'user': 0.0,
        'sys': 0.0,
        'nb': 0
    }

    for file in sys.argv[1:-1]:
        append_times(file, times)

    write_times(sys.argv[-1], times)


def append_times(filename, times):
    def append_exit(match_result):
        value = int(match_result[1])
        if value != 0:
            times['exit'] = value

    def append_time(match_result, category):
        value = float(match_result[1])
        times[category] = times[category] + value

    regex_matches = [
        (r"exit\S+(-?\d+)", append_exit),
        (r"real\s+(-?\d+\.?\d+)", lambda t: append_time(t, 'real')),
        (r"user\s+(-?\d+\.?\d+)", lambda t: append_time(t, 'user')),
        (r"sys\s+(-?\d+\.?\d+)", lambda t: append_time(t, 'sys')),
    ]

    times['nb'] = times['nb'] + 1

    with open(filename) as f:
        for line in f.readlines():
            for regex_match in regex_matches:
                m = re.match(regex_match[0], line)
                if m is not None:
                    regex_match[1](m)
                    break


def write_times(filename, times):
    with open(filename, "w+") as f:
        f.write("exit {}\n".format(times['exit']))
        f.write("real {:>11}".format("{:.4f}\n".format(times['real'])))
        f.write("user {:>11}".format("{:.4f}\n".format(times['user'])))
        f.write("sys  {:>11}".format("{:.4f}\n".format(times['sys'])))
        f.write("Number of programs : {}".format(times['nb']))


if __name__ == '__main__':
    main()
