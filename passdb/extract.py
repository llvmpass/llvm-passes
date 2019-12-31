#! /usr/bin/python3

import clang.cindex
from clang.cindex import CursorKind, TokenKind
from itertools import zip_longest, islice
import sys
import re
import subprocess
import yaml
import os
import csv
import getopt

#
#  Analysis of getAnalysisUsage() methods
#

def parentclassname(decl):
    """
    Syntactically find the name of an inherited class' public parent.

    :param decl clang.cindex.Cursor:
      Cursor to class, structure, or template declaration.
    :returns:
      Name of first parent class if found, None otherwise.
    """

    tokens = list(islice(decl.get_tokens(), 100))

    for t1, t2 in zip(tokens, tokens[1:]):
        if t1.kind == TokenKind.KEYWORD and t1.spelling == "public" and \
            t2.kind == TokenKind.IDENTIFIER:
            return t2.spelling

def classname(c):
    """
    Syntactically find the name and parent name of a class where a method
    declaration is defined.

    :param c clang.cindex.Cursor:
      Cursor to method declaration.
    :returns:
      Name of container class and parent class if found, None otherwise.
    """

    if c is None or c.kind == CursorKind.TRANSLATION_UNIT:
        return None, None
    if c.kind in [ CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL,
        CursorKind.CLASS_TEMPLATE ]:
        return c.spelling, parentclassname(c)
    return classname(c.semantic_parent)

def au_make():
    """Make an empty analysis usage set."""
    return {
        'preserves': [],
        'requires': [],
        'transitive': [],
        'optional': [],
    }

def au_parse(getAnalysisUsage):
    """
    Locate information in the getAnalysisUsage method body of a class.

    :param getAnalysisUsage clang.cindex.Cursor:
      Cursor to method declaration.
    :returns:
      An AnalysisUsage dictionary summing up the declarations.
    """

    au = au_make()

    # Find all calls to addRequired() or addPreserved()
    for c in getAnalysisUsage.walk_preorder():
        if c.kind != CursorKind.COMPOUND_STMT: continue

        # I don't understand why clang doesn't give access to statements...
        tokens = c.get_tokens()
        tokens = [ t for t in tokens if t.kind != TokenKind.PUNCTUATION ]

        for t1, t2 in zip_longest(tokens, tokens[1:]):
            if t1.kind != TokenKind.IDENTIFIER: continue
            if t1.spelling == "setPreservesAll":
                au['preserves'] = ["(all)"]
            if t1.spelling == "setPreservesCFG":
                au['preserves'].append("(cfg)")

            if t2 is None or t2.kind != TokenKind.IDENTIFIER: continue
            if t1.spelling == "addRequired":
                au['requires'].append(t2.spelling)
            if t1.spelling == "addRequiredTransitive":
                au['transitive'].append(t2.spelling)
            if t1.spelling == "addPreserved":
                au['preserves'].append(t2.spelling)
            if t1.spelling == "addUsedIfAvailable":
                au['optional'].append(t2.spelling)

    return au

def info_getAnalysisUsage(filepath):
    """
    Harvest pass information from the getAnalysisUsage() methods of a file.

    :param filepath str:
      Filepath relative to /llvm/lib (eg. "Transforms/Scalar/EarlyCSE.cpp").
    :returns:
      Dictionary with pass symbols as keys and metadata as values.
    """

    idx = clang.cindex.Index.create()
    args = '-xc++ -std=c++11 -I ../../llvm/include -I ../../build/include'
    unit = idx.parse(filepath, args=args.split())

    passes = {}

    for c in unit.cursor.walk_preorder():
        ref = c.referenced
        if ref is None: continue

        if c.kind == CursorKind.CXX_METHOD:
            # Find getAnalysisUsage() method declarations or definitions
            method_name = ref.spelling
            if method_name != 'getAnalysisUsage': continue

            # Require the passname to continue
            passname, parentclass = classname(c.referenced)
            if passname is None: continue

            # Extend the pass dictionary with analysis results
            data = au_parse(c)
            data['parent'] = parentclass
            passes[passname] = data

    return passes

#
#  Analysis of INITIALIZE_PASS macros
#

# Header placed before the calls to INITIALIZE in the source file. By running
# the preprocessor on this we can extract relevant information from the calls.
preprocessor_pattern = """
#define INITIALIZE_PASS_BEGIN(sym, argt, _1, _2, an) \\
  #sym : {{ "file": "{}", "arg": argt, "analysis": an, "deps": [

#define INITIALIZE_PASS_DEPENDENCY(sym) #sym,

#define INITIALIZE_PASS_END(...) ] }},

#define INITIALIZE_PASS_WITH_OPTIONS(...) \\
  INITIALIZE_PASS(__VA_ARGS__)
#define INITIALIZE_PASS_WITH_OPTIONS_BEGIN(...) \\
  INITIALIZE_PASS_BEGIN(__VA_ARGS__)
#define INITIALIZE_PASS_WITH_OPTIONS_END(...) \\
  INITIALIZE_PASS_END(__VA_ARGS__)

#define INITIALIZE_PASS(...) \\
  INITIALIZE_PASS_BEGIN(__VA_ARGS__) \\
  INITIALIZE_PASS_END(__VA_ARGS__)
"""

# The [opt] argument (eg. "deadargelim") defined in the INITIALIZE call is
# often specified as a macro, so we need to copy it for the substitution to
# occur when CPP is invoked. This is a list of names of such macros.
preprocessor_names = """
    DEBUG_TYPE ORE_NAME FIXUPLEA_NAME FIXUPBW_NAME EVEX2VEX_NAME SV_NAME
    LV_NAME LDIST_NAME AA_NAME LAA_NAME CM_NAME DL_NAME LLE_OPTION LVER_OPTION
    PASS_KEY
""".split()

def info_INITIALIZE(filepath):
    """
    Harvest metadata from the INITIALIZE_PASS macros with the C preprocessor.

    :param filepath str:
      Filepath relative to /llvm/lib (eg. "Transforms/Scalar/EarlyCSE.cpp").
    :returns:
      Dictionary with pass symbols as keys and metadata as values.
    """

    with open(filepath, 'r') as fp:
        code = fp.read()

    # Find all INITIALIZE macros
    pattern = r'INITIALIZE_PASS[A-Z_]*\s*\(.*?\)$'
    matches = re.findall(pattern, code, re.MULTILINE | re.DOTALL)
    macros = "\n".join(matches)

    # From these macro calls, remove trailing semicolons at end of line, this
    # messes up the results of the preprocessing.
    macros = macros.replace(';\n', '\n')

    # Also find the macro that defines the [opt] argument.
    # Since there is one file that undefines it then redefines it with another
    # value, also catch #undefs.
    pattern = r'#(?:define|undef)\s*(?:'+'|'.join(preprocessor_names)+').*$'
    matches = re.findall(pattern, code, re.MULTILINE)
    predef = "\n".join(matches)

    # Give the header and the macros as input to CPP
    input = predef + preprocessor_pattern.format(filepath) + macros
    input = bytes(input, encoding='utf8')

    p = subprocess.run("cpp -P".split(), input=input, stdout=subprocess.PIPE)
    x = "{" + p.stdout.decode() + "}"

    # TODO: Look for other options (JSON doesn't like trailing commas)
    x = eval(x, {}, {'false': False, 'true': True})

    # In Transforms/Utils/LoopUtils.cpp there is a series of calls to
    # INITIALIZE_PASS_DEPENDENCY without INITIALIZE_PASS_BEGIN, and somehow
    # that makes "x" the representation of a set. We don't want it.
    return x if type(x) is dict else dict()

#
#  Complete analysis
#

def merge(init, au):
    """Merge the info of dicts from getAnalysisUsage() and INITIALIZE."""

    # Extend the "requires" from the getAnalysisUsage() method with the
    # INITIALIZE_PASS_DEPENDENCY() values obtained from initialization.
    au['requires'] = list(set(au['requires'] + init['deps']))
    del init['deps']

    # Other attributes don't conflict, just merge.
    return { **init, **au }

def info(filepath):
    """
    Harvest information from a pass source file.

    :filepath:
      Filepath relative to /llvm/lib (eg. "Transforms/Scalar/EarlyCSE.cpp").
    :returns:
      Dictionary with pass symbols as keys and metadata as values.
    """

    init = info_INITIALIZE(filepath)
    au = info_getAnalysisUsage(filepath)

    # Merge everything by name
    data = { name: merge(init[name], au.get(name,au_make())) for name in init }

    if data:
        print(yaml.dump(data))

#
#  Main program
#

usage_string = f"""
usage: {sys.argv[0]} -e [-a] [<llvm library directory>]
       {sys.argv[0]} -s <relative file path> [<llvm library directory>]
       {sys.argv[0]} -c <generated yaml file> <output directory>

Traverses pass source files from the LLVM library and outputs metadata and
dependencies in YAML format for all passes found, on stdout. With -s, analyzes
a single file. With -c, converts the generated YAML to CSV files for Neo4j.

Options for extraction mode:
  -e   Specifies extraction mode
  -a   Traverse all folders (default is only Analysis/ IR/ and Transforms/)

  The LLVM directory should be /llvm/lib where / denotes the repository root.
  It is guessed automatically with Git if not specified.

Options for single extraction mode:
  -s   Specifies single extraction mode

  The file path should be specified relative to /llvm/lib, for instance
  "Transforms/Scalar/EarlyCSE.cpp". As for extraction mode, the LLVM directory
  can be left to guess with Git or specified explicitly.

Options for conversion mode:
  -c   Specifies conversion mode

  The generated YAML file is obtained by redirecting the output of extraction
  mode to a file. The result of conversion is several CSV files that are stored
  in the specified directory.
""".strip()

def err(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)

def usage(exitcode=1):
    err(usage_string)
    sys.exit(exitcode)

def fail(message):
    err(f'error: {message}')
    err(f"Try '{sys.argv[0]} --help' for more information.")
    sys.exit(1)

def cmd(cmd):
    """Execute a command and return its standard output"""
    p = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    out, err = p.communicate()
    return out.decode('utf8').strip()

def guess_llvm_path():
    err('No LLVM directory specified, going to guess with Git.')
    path = cmd('git rev-parse --show-toplevel') + '/llvm/lib'
    err(f'Guessed directory: {path}\n')
    return path


if len(sys.argv) == 1:
    usage(0)

#-

llvm = None

opts, args = getopt.gnu_getopt(sys.argv[1:], "easc")
opts = "".join(o[0][1] for o in opts)

total = ('e' in opts) + ('s' in opts) + ('c' in opts)

if total < 1:
    fail('Please specifiy one of -e, -s or -c')
if total > 1:
    fail('Please specify only one of -e, -s and -c')

# Extraction mode

if 'e' in opts:
    # Guess the LLVM path via Git if not specified
    os.chdir(args[0] if args else guess_llvm_path())

    # Get a list of cpp files to analyze
    dirs = '' if 'a' in opts else 'Analysis IR Transforms'
    files = cmd(f'find {dirs} -name *.cpp')

    # Dump everything!
    for filepath in files.split():
        err(f'Next file: {filepath}')
        info(filepath)

# Single extraction mode

elif 's' in opts:
    if len(args) < 1:
        fail('Please specify a file to analyze with -s.')

    # Guess the LLVM directory if not specified
    os.chdir(args[1] if len(args) >= 2 else guess_llvm_path())

    # Analyze the specified file
    info(args[0])

# Conversion mode

elif 'c' in opts:
    if len(args) < 1:
        fail('Please specify a generated YAML file to dump with -c.')
    if len(args) < 2:
        fail('Please specify a name for the output directory.')

    out = args[1]
    cmd(f"mkdir -p {out}")

    with open(args[0], 'r') as fp:
        data = yaml.load(fp.read())

    # Write nodes
    with open(f'{out}/passes.csv', 'w') as fp:
        fields = 'name analysis arg file parent'.split()

        writer = csv.DictWriter(fp, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()

        for name in data:
            writer.writerow({ 'name': name, **data[name] })

    # Automated function to write relations
    def rel(fp, field):
        writer = csv.DictWriter(fp, fieldnames='name link'.split(),
            extrasaction='ignore')
        writer.writeheader()

        for name in data:
            for link in data[name][field]:
                writer.writerow({ 'name': name, 'link': link })

    # Write relations
    with open(f'{out}/requires.csv', 'w') as fp:
        rel(fp, 'requires')
    with open(f'{out}/transitive.csv', 'w') as fp:
        rel(fp, 'transitive')
    with open(f'{out}/preserves.csv', 'w') as fp:
        rel(fp, 'preserves')
    with open(f'{out}/optional.csv', 'w') as fp:
        rel(fp, 'optional')
