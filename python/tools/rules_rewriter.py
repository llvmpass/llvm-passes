import os
import re
import sys

from enum import Enum

"""
This script rewrites the rules inside the [rules.ninja] file generated by Ninja
to replace the standard clang execution by a custom script.
"""

def rewrite_ninja(ninja_file, script_name='main.sh'):
    """
    Rewrite the given Ninja file to replace build rules by calls to the
    provided script.

    :param ninja_file:  The ninja file to rewrite
    :param script_name: Name of compilation script in /testsuite-scripts
    """
    new_ninja_content = []

    class Mode(Enum):
        look_for_compile_rule = 0
        look_for_command_rewriting = 1

    mode = Mode.look_for_compile_rule

    with open(ninja_file) as file:
        for line in file.readlines():
            # Continue = we don't append the line. If we let the instructions go, the line will be append to the
            # new ninja content array
            if mode == Mode.look_for_compile_rule:
                # We rewrite the command of every rules but timeit
                if (line.startswith('rule C_COMPILER__') and not line.startswith('rule C_COMPILER__timeit')) \
                        or line.startswith('rule CXX_COMPILER_'):
                    mode = Mode.look_for_command_rewriting
            elif mode == Mode.look_for_command_rewriting:
                if line.strip().startswith('command = '):
                    new_line = read_and_rewrite_command(line, script_name)

                    if new_line is None:
                        raise Exception("Invalid command line : " + line)

                    new_ninja_content.append(new_line)
                    mode = Mode.look_for_compile_rule
                    continue
            else:
                raise Exception('Unknown mode ' + str(mode))

            new_ninja_content.append(line)

    # Write the new ninja file
    file = open(ninja_file, "w")
    file.write("".join(new_ninja_content))
    file.close()


def read_and_rewrite_command(command, script_name):
    """
    Rewrite a single command.

    :param command:     Original command line
    :param script_name: Name of compilation script
    :return:            Rewritten command if it's a compialtion command, None otherwise
    """

    regex_read = read_command_with_regex(command)
    if regex_read is None:
        return None

    # Return a generic command that calls the provided script
    MD, clang, timeit = regex_read['MD'], regex_read['clang'], regex_read['timeit']
    root = os.path.dirname(os.path.dirname(os.path.dirname(clang)))

    args = "in out DEFINES INCLUDES FLAGS DEP_FILE".split()
    the_command = f'{root}/testsuite-scripts/{script_name} '
    the_command += ' '.join(map(lambda x: f'"${x}"', args))
    the_command += f' "{MD}" "{clang}"'
    return f'  command = {the_command}\n'

def read_command_with_regex(command):
    """
    Parse a compilation command and return the useful components: path to
    timeit, to clang, and the -MD or -MMD flag for dependency generation.

    :param command: Original command line
    :return:        Dictionary with timeit path, clang path and MD flag if it's
                    compilation command, None otherwise.
    """

    # TODO: use \w for where applicable
    REGEX = 'command = ([-A-Za-z0-9_\\/+]*timeit) --summary \\$out\\.time ([-A-Za-z_0-9\/\\.+]*) ' \
            '\\$DEFINES \\$INCLUDES \\$FLAGS (\\-M*D)? -MT \\$out -MF \\$DEP_FILE -o \\$out -c \\$in'

    PROPER_REGEX = REGEX.replace(" ", "\\s+")

    result = re.findall(PROPER_REGEX, command)

    if not result:
        return None

    # Retrieve the MD flag because some Ubuntu distributions use -MD while others use -MMD.
    return {
        'timeit': result[0][0],
        'clang':  result[0][1],
        'MD':     result[0][2],
    }
