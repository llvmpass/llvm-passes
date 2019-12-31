#! /usr/bin/env python3
import filecmp
import os
import shutil
import subprocess
import sys

'''
    A simple tool to study which pass does an effect
    
    First arg = .c file
    Others args = sequence of opt to apply
    
    An alternative without any script (but prints after every opt) :
    opt source.ll -print-after-all [some opt] -o dest.ll -print-regusage
    
    This script modify the content of the temp folder where it is executed.
    
    It is more an experimental tool than a proper script, explaining why it is not that user friendly
'''

PRINT_OPT_CALL = False          # Prints every call to opt
PRINT_DIFF_ON_CHANGE = True     # Prints diff when the IR changes
PRINT_FIRST_IR = True           # Prints the first IR
DEBUG_PASS_ARGUMENTS = False    # If true, -debug-pass=Arguments is passed to opt to print the actually executed passes
TEMP_FOLDER_NAME = "temp"


def clean_temp_folder():
    shutil.rmtree(TEMP_FOLDER_NAME, ignore_errors=True)
    os.mkdir(TEMP_FOLDER_NAME)


def p(filename):
    return os.path.join(TEMP_FOLDER_NAME, filename)


def build_ll(bc_file, ll_file):
    subprocess.call(["llvm-dis", p(bc_file), "-o", p(ll_file), "-disable-ondemand-mds-loading", "-show-annotations"])




def opt_call(opt):
    if PRINT_OPT_CALL:
        print(":: opt {}", opt)

    if DEBUG_PASS_ARGUMENTS:
        opt_command = ["opt", opt, p("_src.bc"), "-o", p("_dst.bc"), "-debug-pass=Arguments"]
    else:
        opt_command = ["opt", opt, p("_src.bc"), "-o", p("_dst.bc")]

    subprocess.call(opt_command)


def shift():
    os.rename(p("_dst.bc"), p("_src.bc"))
    os.rename(p("_dst.ll"), p("_src.ll"))


def save(opt_list: list, step, last_modif_step=None, file="_dst.ll"):
    shutil.copyfile(p(file), p("opt_{step:02d}.ll".format(step=step)))
    if PRINT_DIFF_ON_CHANGE:
        print("========== Changed at step {} : {}".format(step, " ".join(opt_list)))
    if last_modif_step is not None:
        if PRINT_DIFF_ON_CHANGE:
            subprocess.call(["diff", p("opt_{step:02d}.ll".format(step=last_modif_step)),
                             p("_dst.ll"), "--color=always"])
    opt_list.clear()

def main():
    if len(sys.argv) < 3:
        print("Usage : {} /path/to/program.c opts_list_to_apply".format(sys.argv[0]))
        exit(0)

    program = sys.argv[1]
    opts_to_apply = sys.argv[2:]

    clean_temp_folder()

    # Build a bc file
    subprocess.call(["clang", "-emit-llvm", program, "-c", "-o", p("_src.bc"), "-O0", "-Xclang", "-disable-O0-optnone"])
    build_ll("_src.bc", "_src.ll")
    save([], 0, None, "_src.ll")

    if PRINT_FIRST_IR:
        subprocess.call(['cat', p('_src.ll')])

    opt_list = []

    last_modif_step = 0
    step = 1
    for opt in opts_to_apply:
        if opt == "-targetpassconfig":
            continue

        opt_list.append(opt)
        opt_call(opt)
        build_ll("_dst.bc", "_dst.ll")

        if not filecmp.cmp(p("_src.ll"), p("_dst.ll"), shallow=False):
            save(opt_list, step, last_modif_step)
            last_modif_step = step

        shift()
        step = step + 1


if __name__ == '__main__':
    main()