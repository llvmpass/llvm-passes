#! /usr/bin/env python3
import time
import re
import sys
import subprocess
import os
import argparse
import shlex
from subprocess import DEVNULL

import tools.rules_rewriter as rules_rewriter

'''
    Compare the execution time of two executables that we compile from the same source file and print the result

    Note : With -O0, objcopy displays "Failed to find link section for section 8" but it doesn't stop the process and
    main renaming works.
'''


# ======================================================================================================================
# -- COMPILATION  -- COMPILATION  -- COMPILATION  -- COMPILATION  -- COMPILATION  -- COMPILATION  -- COMPILATION


# Execute the given command and print it
def execute_command(command):
    if hasattr(execute_command, "verbose"):  # We use an attribute of the function to avoid passing verbose every time
        print(command)

    subprocess.call(command)


# Compile with the given option the given .c source file to the object_file
def start_compiling_with_o(source, object_file, option):
    args = ["clang", "-c", source, "-o", object_file]

    # As this function is also used without any option, this check is needed to know if we are actually starting a
    # compilation
    if option is not None:
        args.append(option)

    execute_command(args)


def start_compiling_to_ir(source, bc_file):
    execute_command(["clang", "-emit-llvm", source, "-c", "-o", bc_file, "-O0", "-Xclang", "-disable-O0-optnone"])


def run_optimizations(bc_file, list_of_passes):
    arguments = ["opt"]
    arguments.extend(list_of_passes)
    arguments.extend(["-O0", bc_file, "-o", bc_file])  # We append -O0 to disable any further optimization on this file

    execute_command(arguments)


def compile_bc_to_o_file(bc_file, o_file):
    start_compiling_with_o(bc_file, o_file, None)


# Takes the object file, links and compile by wrapping its main in the wrapper_file with number_of_loops loops.
def link_with_wrapper(object_file, destination, wrapper_file, number_of_loops):
    owrapper = "wrapper.o"

    # Redefine main function to wrap the original main, wrap the main file and compile
    execute_command(["objcopy", "--redefine-sym", "main=old_main", object_file])
    execute_command(["clang", "-c", wrapper_file, "-o", owrapper, "-D", "NUMBER_OF_ITERATIONS="+str(number_of_loops)])
    execute_command(["clang", owrapper, object_file, "-o", destination])

    # Clean compilation objects
    os.remove(object_file)
    os.remove(owrapper)


# Finish the compilation of the object_file by compiling it to an executable without any linking
def finish_compilation(object_file, destination, remove_object_file=True):
    execute_command(["clang", object_file, "-o", destination])
    if remove_object_file:
        os.remove(object_file)


# Compile the source file by modifying the main function from main to entry_point
def compile_with_redefined_main(source, destination, option, number_of_loops, wrapper_file):
    ofilename = destination + ".o"

    start_compiling_with_o(source, ofilename, option)
    link_with_wrapper(ofilename, destination, wrapper_file, number_of_loops)


def normal_compilation(source, destination, option):
    subprocess.call(["clang", "-o", destination, source, option])
    return destination


# ======================================================================================================================
# -- MEASURING FUNCTIONS-- MEASURING FUNCTIONS  -- MEASURING FUNCTIONS  -- MEASURING FUNCTIONS  -- MEASURING FUNCTIONS


# Measure the execution time by resorting to the wrapping main
def measure_execution_time_with_wrapped_function(executable):
    # Run wrapped executable
    subprocess.call(["./" + executable], stdout=DEVNULL, stderr=DEVNULL)

    # Get x in "Elapsed time (ns) : x" line of wrappertime.txt
    elapsed_time_line = "Elapsed time (ns) : "

    with open("wrappertime.txt", "r") as file_lines:
        for line in file_lines:
            if line.startswith(elapsed_time_line):
                return int(line[len(elapsed_time_line):]) / 1000000

    return None


# Measure the minimum time used to run the given executable using the time function of python
def measure_execution_time_python(executable, number_of_benchmark):
    min_time = None

    for _ in range(max(1, number_of_benchmark)):
        t0 = time.time()
        subprocess.call(["./" + executable], stdout=DEVNULL)
        t1 = time.time()

        run_time = (t1 - t0) * 1000

        if min_time is None or min_time > run_time:
            min_time = run_time

    return min_time


# Measure the maximum heap usage of the executable
def measure_max_stack_usage(executable):
    # Execute valgrind with massif tool to mesure stack size
    command = ["valgrind", "--tool=massif", "--stacks=yes", "./" + executable]

    pipe = subprocess.Popen(command, stdout=DEVNULL, stderr=subprocess.PIPE)
    output = pipe.communicate()[1]

    # Get massif file generated name
    process_number = re.search("==([0123456789]+)==", str(output)).group(1)
    massif_file = "massif.out." + process_number

    # Extract the maximum mem_stacks_B from massif file
    max_stack_size = 0

    with open(massif_file, "r") as file_lines:
        beginning = "mem_stacks_B="
        length = len(beginning)

        for line in file_lines:
            if line.startswith(beginning):
                max_stack_size = max(max_stack_size, int(line[length:]))

    # Clean up
    os.remove(massif_file)

    return max_stack_size


# Measure the size of the .text section of the executable using readelf
def measure_text_section_size(executable):
    # Run readelf
    command = ["readelf", "-S", executable]
    output = subprocess.check_output(command, stderr=DEVNULL)

    # Extract from input .text section size
    next_section_is_text = False

    for line in output.splitlines():
        line = str(line)

        if next_section_is_text:
            section_size = re.search(" ([0123456789abcdef]+)", line)
            if section_size is None:  # Unexpected readelf structure
                print("Unexpected readelf structure : No number found in the line after .text", file=sys.stderr)
                return None
            else:
                return int(section_size.group(1), 16)

        if ".text" in line:
            next_section_is_text = True

    # Return result
    print("Unexpected readelf structure : No .text line or .text is the last line", file=sys.stderr)
    return None


# ======================================================================================================================
# -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV  -- CSV


# Write in the csv file the results of the experiment
def fill_csv(csv_file_name, args, measures):
    if args.existing_opt is not None:
        compile_option = args.existing_opt
    else:
        compile_option = ";".join(args.opt)

    write_header = not os.path.isfile(csv_file_name)

    file = open(csv_file_name, "a")

    if write_header:
        file.write(
            "//File\tOption\tTime with wrapping in ms\tTime with python in ms\tMax stack size\t.text section size\n")

    csv_line = "%s\t%s\t%lf\t%lf\t%d\t%d\n"
    args_txt = (args.c_file, compile_option, measures[0], measures[1], measures[2], measures[3])
    file.write(csv_line % args_txt)

    file.close()


# ======================================================================================================================
# -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN  -- MAIN


def compile_c_file(args):
    """
    Compile the required source file with the required parameters
    :param args: The decoding of the args
    :return: The name of the two c executable (one wrapped, one not)
    """
    if args.existing_opt is not None:
        # Regular O optionn, we can directly use clang
        product_file = "temp.o"
        start_compiling_with_o(args.c_file, product_file, args.existing_opt)
    else:
        # A list of passes requires to use opt
        product_file = "temp.bc"
        start_compiling_to_ir(args.c_file, product_file)
        run_optimizations(product_file, args.opt_friendly_opt)

        # objcopy can't modify main in a bc file so we compile to an o file
        compile_bc_to_o_file(product_file, product_file + ".o")
        os.remove(product_file)
        product_file = product_file + ".o"

    finish_compilation(product_file, "executable", False)
    link_with_wrapper(product_file, "wrapped_executable", args.wrapper, args.number)

    return "executable", "wrapped_executable"


def measure_c_file(args):
    """
    Measure the performance of a given source file that will be compiled using the passed args
    :param args: The arg decoding of the args
    :return: A tuple with (time measured with c wrapping, time measures by python, max stack usage, executable size)
    """
    # Compilation
    regular_exec, wrapped_exec = compile_c_file(args)

    # Measures
    min_elapsed_time_wr = measure_execution_time_with_wrapped_function(wrapped_exec)
    min_elapsed_time = measure_execution_time_python(regular_exec, args.number)
    stack_size = measure_max_stack_usage(regular_exec)
    text_size = measure_text_section_size(regular_exec)

    return min_elapsed_time_wr, min_elapsed_time, stack_size, text_size


def measure_a_file(args_result):
    """
    Compiles the required file, measure its performance and display it on screen / in a csv file
    :param args_result: The result of arg parse
    """
    measures = measure_c_file(args_result)

    if not args_result.quiet:
        print("Time (wr) : %lf ms\nTime (py) : %lf ms\nStack size : %d\n.text size : %d" % measures)

    if args_result.csv is not None:
        fill_csv(args_result.csv, args_result, measures)


def decrypt_opt_list(opt_list: str):
    """
    Decrypt the opt list by separating their name and using the same process as rule rewriter to decrypt the passes.
    This approach enables to have the same definition of a pass list in the two main compilation module of the scripts
    :param opt_list: The list of opt, ideally separated with a space (but using the bash format). A name starting with
    - is an argument for opt, A name starting with any other character is the name of a file which contains the opt to
    apply
    :return: A list of passes to pass to the opt of llvm
    """
    split_str = shlex.split(opt_list)
    return rules_rewriter.build_passes_from_list(split_str)


# Builds the arg parser
def make_arg_parser():
    """
    Build the arg parser for this script
    :return: The arg parser
    """
    arg_parser = argparse.ArgumentParser(description="This python script is intended to measure the time of execution "
                                                     "of a compiled executable with clang by manipulating the order of "
                                                     "passes. This will builds executable in the current folder",
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    arg_parser.add_argument(action="store", dest="c_file", help=".c file")
    arg_parser.add_argument('-w', '--wrapper', default=os.path.join(sys.path[0], 'tools/wrapper.c'),
                            help="Wrapper file used to measure the execution time of the c file. The wrapper is "
                                 "expected to measure the execution time several times and avoid having to use "
                                 "fork/exec during the different tests to start the program.")

    arg_parser.add_argument('-n', '--number', action='store', type=int, help="Changes the number of benchmarks",
                            default=1)

    opt_group = arg_parser.add_mutually_exclusive_group(required=True)
    opt_group.add_argument('-O0', dest="existing_opt", action="store_const", const="-O0", help="Compiles with O0")
    opt_group.add_argument('-O1', dest="existing_opt", action="store_const", const="-O1", help="Compiles with O1")
    opt_group.add_argument('-O2', dest="existing_opt", action="store_const", const="-O2", help="Compiles with O2")
    opt_group.add_argument('-O3', dest="existing_opt", action="store_const", const="-O3", help="Compiles with O3",
                           default="-O3")
    opt_group.add_argument('-opt', dest="opt", action="store", help="Compiles using opt and the following given opt. "
                                                                    "Arguments starting with a - are treated as a raw "
                                                                    "argument for opt. Other arguments are treated as "
                                                                    "files that contains opt. "
                                                                    "To start with an existing -existing_opt, you can "
                                                                    "use -opt=\"-existing_opt\"")
    verbose_group = arg_parser.add_mutually_exclusive_group()
    verbose_group.add_argument('-v', '--verbose', action='store_true', help="Print in console run commands")
    verbose_group.add_argument('-q', '--quiet', action='store_true', help="Do not print results in console")

    arg_parser.add_argument('-c', '--csv', action='store', help="Prints the result in the given csv file")

    return arg_parser


def main():
    """
    Main function
    """
    arg_parser = make_arg_parser()
    args_result = arg_parser.parse_args()

    if args_result.existing_opt is None:
        # If we don't use a real opt (O0 to O3), we want to decrypt the opt list from the user
        args_result.opt_friendly_opt = decrypt_opt_list(args_result.opt)

    if args_result.verbose:  # Ask execute_command to print its command
        execute_command.verbose = True

    measure_a_file(args_result)


if __name__ == '__main__':
    main()
