#! /usr/bin/env python3
import subprocess
import argparse
import os
from time import gmtime, strftime


'''
    This script is just a script that launch llvm-lit until the end of the universe on some folders
'''

THIS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/"


def run_a_test_suite(folder, json_name_format, iteration_number, sub_folder, llvm_lit_path):
    print("- Run " + folder)
    json_name = json_name_format.format(iteration_number)
    command = [llvm_lit_path, "-s", "-o", json_name, sub_folder]
    subprocess.call(command, cwd=folder)


def run_all_test_suites(folders, json_name_format, number_of_iterations, sub_folder, llvm_lit_path):
    i = 0

    # number_of_iterations == 0 means infinite
    while number_of_iterations == 0 or i != number_of_iterations:
        if number_of_iterations == 0:
            print("== Iteration " + str(i + 1))
        else:
            print("== Iteration " + str(i + 1) + " / " + str(number_of_iterations))

        for test_suite in folders:
            print(test_suite)
            run_a_test_suite(test_suite, json_name_format, i, sub_folder, llvm_lit_path)

        i = i + 1


def _main():
    arg_parser = argparse.ArgumentParser(description="Runs the test suite")
    arg_parser.add_argument('-l', '--llvm-lit', action="store",
                            help="The path to the llvm-lit executable. If not specified, the script will try to use the"
                                 " llvm-lit found in path")
    arg_parser.add_argument('-n', '--number', action="store", type=int, default=[0], nargs=1,
                            help="The number of time each test-suite will be run. If equals to 0, the script will run "
                                 "until stopped by ctrl+c.")
    arg_parser.add_argument('-f', '--folder', action="store", default=".",
                            help="Folder in which llvm-lit will be started. By default, llvm-lit runs the whole test "
                                 "suite")
    arg_parser.add_argument(dest="test_suite_path", action="append", nargs="+",
                            help="Path to the benchmarked test suite")

    parsed_args = arg_parser.parse_args()

    print(parsed_args)

    current_date = strftime("%Y-%m-%d-%H-%M-%S", gmtime())

    if parsed_args.llvm_lit is None:
        llvm_lit_path = 'llvm-lit'
    else:
        llvm_lit_path = os.path.abspath(os.path.join(os.getcwd(), parsed_args.llvm_lit))

    run_all_test_suites(parsed_args.test_suite_path[0], "run_" + current_date + "_{:03d}.json", parsed_args.number[0],
                        parsed_args.folder, llvm_lit_path)


if __name__ == '__main__':
    _main()
