#! /usr/bin/env python

# Please see COPYRIGHT information at the end of this file
# File: config_pynamic.py
# Authors: Dong H. Ahn and Greg Lee
#
# An addon to pyMPI, which allows dynamic library linking system
# stress test.
#
# command: ./config_pynamic.py generates shared library
#          codes, builds shared libraries using those codes, and then
#          configures/builds pyMPI with those libraries.
#

# from so_generator import print_error, parse_and_run, run_command
import sys
import os
import argparse
from pathlib import Path
import random
import multiprocessing as mp

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate Pynamic shared libraries and configure/build', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("num_files", type=int, help="Total number of shared objects to produce")
    parser.add_argument("avg_num_functions", type=int, help="Average number of functions per shared object")

    parser.add_argument("-b", "--big-exe", action="store_true",
                        help="Generate the pynamic-bigexe-pyMPI and pynamic-bigexe-sdb-pyMPI executables")

    parser.add_argument("-d","--depth", type=int, default=10,
                        help="Maximum Pynamic call stack depth")

    parser.add_argument("-e","--external", action="store_true",
                        help="Enable external functions to call across modules")

    parser.add_argument("-i", metavar="python_include_dir",
                        help="Add <python_include_dir> when compiling modules")

    parser.add_argument("-j", metavar="[N]", type=int,
                        help="Build in parallel with a max of <N> processes")

    parser.add_argument("-n", dest="name_length", default=0, metavar="[N]", type=int,
                        help="Add <N> characters to the function names")

    parser.add_argument("-p", "--print", action="store_true",
                        help="Add a print statement to every generated function")

    parser.add_argument("-s", "--seed", type=int,
                        help="Seed to the random number generator")

    parser.add_argument("-u", nargs=2, type=int, metavar=('num_utility_mods', 'avg_num_u_functions'),
                        help="Create utility modules with an average number of functions")

    parser.add_argument("--with-cc", metavar="[command]",
                        help="Use the C compiler located at <command> to build Pynamic modules")

    parser.add_argument("--with-python", metavar="[command]",
                        help="Use the Python interpreter located at <command> to build Pynamic modules")

    parser.add_argument("-c", nargs=argparse.REMAINDER,
                        help="Pass whitespace-separated list of configure options to configure when building pyMPI")

    return parser.parse_args()

def clean_pynamic_files() -> None:
    """
    Removes specific files from the current directory that match predefined naming patterns.

    This function scans files in the current directory and deletes those that include specific
    substrings in their names, such as 'libmodule', 'libutility', 'pynamic.h', or 'libpynamic.a'.
    Files named specifically as 'libmodulefinal.c' or 'libmodulebegin.c' are excluded from
    deletion.

    Raises:
        OSError: If issues occur during file deletion.
    """
    top_dir = Path('.')
    for file in top_dir.iterdir():
        if file.is_file():
            name = file.name
            if (
                any(sub in name for sub in ('libmodule', 'libutility', 'pynamic.h', 'libpynamic.a')) and
                'libmodulefinal.c' not in name and
                'libmodulebegin.c' not in name
            ):
                file.unlink()

def create_function_list(num_files) -> list:
    """
    Generates a list of function signatures with random return types and arguments.

    Args:
        num_files (int): Number of random function signatures to generate.

    Returns:
        list: A list where each element represents a function signature. The first element is the return type,
        the second element is the number of arguments, and the subsequent
        elements are the types of these arguments.
    """
    var_types = ['int', 'long', 'float', 'double', 'char *']
    return [
        [return_type := random.choice(var_types), num_args := random.randint(0, 5)] +
        [random.choice(var_types) for _ in range(num_args)]
        for _ in range(num_files)
    ]

def create_function_declaration(function_name, function_signature):
    # Signature is of the form [return_type, num_args, arg_type1, arg_type2, ...]
    return_type = function_signature[0]
    arg_types = function_signature[2:]

    args_str = ", ".join(f"{arg_type} arg{i}" for i, arg_type in enumerate(arg_types))

    return f"{return_type} {function_name}({args_str})"

def create_function_call(function_name, function_signature):
    return_type = function_signature[0]
    arg_types = function_signature[2:]
    args = []

    type_generators = {
        "int": lambda: f"{random.randint(-1000, 1000)}",
        "long": lambda: f"{random.randint(-1000, 1000)}",
        "float": lambda: f"{round(random.uniform(-1e6, 1e6), 6)}",
        "double": lambda: f"{round(random.uniform(-1e6, 1e6), 6)}",
        "char *": lambda: f"\"{''.join(random.choices('abcdefghijk', k=8))}\"",
    }

    for arg_type in arg_types:
        generator = type_generators.get(arg_type)
        args.append(generator())

    args_str = ", ".join(args)

    return f"{return_type} {function_name}_val = {function_name}({args_str});"


def generate_utility_file(identity: int, avg_num_functions: int, name_length: int, print: bool = False):
    global utility_list
    filename = 'libutility' + str(identity)
    num_functions = random.randint(avg_num_functions // 2, (avg_num_functions * 3) // 2)
    functions = create_function_list(num_functions)
    # utility_list.append(functions)
    function_names = []
    for index, function in enumerate(functions):
        random_digits = ''.join(random.choices('0123456789', k=name_length))
        function_names.append(filename + '_fun' + str(index) + random_digits)
    utility_list.append(zip(function_names, functions))

    # Generate the Header file and Function declarations
    with open(filename + '.h', 'w') as h_file:
        h_file.write('#include <stdio.h>\n#include <stdlib.h>\n\n')
        for index, function in enumerate(functions):
            h_file.write(create_function_declaration(function_names[index], function) + ';\n')

    with open(filename + '.c', 'w') as c_file:
        c_file.write('#include "' + filename + '.h"\n\n')
        for index, function in enumerate(functions):
            c_file.write(create_function_declaration(function_names[index], functions[0]) + ' {\n')
            c_file.write('\t' + function[0] + ' ret_val;\n')
            c_file.write(
                "\tint a, b, c, loop;\n"
                "\tfloat d = 0.0, e = 1.0, f = 2.0;\n"
                "\tdouble g = 0.0, h = 3.0, i = 4.0;\n"
                "\tchar j[10], k[100], l[10][10];\n\n"
            )

            if print:
                c_file.write('\tprintf("In module ' + filename + ' function ' + function_names[index] + '\\n");\n')
            c_file.write(
                "\tfor (loop = 0; loop < 10; loop++)\n"
                "\t{\n"
                "\t\ta = loop;\n"
                "\t}\n"
            )

            if function != functions[-1]:
                f_call = create_function_call(function_names[index + 1], functions[index + 1])
                c_file.write('\t' + f_call + ';\n')
            c_file.write('\treturn ret_val;\n}\n\n')

def generate_module_file(util_enabled: bool, extern: bool, identity: int, avg_num_functions: int, name_length: int, print: bool = False):
    global extern_list
    global utility_list
    filename = 'libmodule' + str(identity)
    num_functions = random.randint(avg_num_functions // 2, (avg_num_functions * 3) // 2)
    functions = create_function_list(num_functions)
    function_names = []
    for index, function in enumerate(functions):
        random_digits = ''.join(random.choices('0123456789', k=name_length))
        function_names.append(filename + '_fun' + str(index) + random_digits)

    with open(filename + '.c', 'w') as c_file:
        c_file.write('#include <Python.h>\n')
        if util_enabled:
            c_file.write('#include "pynamic.h"\n')
        if extern:
            if identity != 0:
                c_file.write('extern ')
                decl = create_function_declaration( f"libmodule{identity -1}_extern", extern_list[identity - 1] )
                c_file.write(decl + ";\n")
            c_file.write(create_function_declaration(filename + "_extern", extern_list[identity]))
            c_file.write(f"\n{{\n\t {extern_list[identity][0]} ret_val;")
            if print:
                c_file.write(f"\tprintf('I am {filename}_extern called from another module\\n');\n")
            c_file.write('\treturn ret_val;\n}\n\n')

        for index, function in enumerate(functions):
            c_file.write(create_function_declaration(function_names[index], function) + ";\n")
            c_file.write("\n")

        for index, function in enumerate(functions):
            c_file.write(create_function_declaration(function_names[index], function) + "{\n")
            c_file.write('\t' + function[0] + ' ret_val;\n')
            c_file.write(
                "\tint a, b, c, loop;\n"
                "\tfloat d = 0.0, e = 1.0, f = 2.0;\n"
                "\tdouble g = 0.0, h = 3.0, i = 4.0;\n"
                "\tchar j[10], k[100], l[10][10];\n\n"
            )
            if print:
                c_file.write('\tprintf("In module ' + filename + ' function ' + function_names[index] + '\\n");\n')
            c_file.write(
                "\tfor (loop = 0; loop < 10; loop++)\n"
                "\t{\n"
                "\t\ta = loop;\n"
            )

            if util_enabled:
                utility_file = random.choice(utility_list)
                # utility_call = create_function_call( , )





def generate_shared_objects(parser):
    if parser.seed:
        random.seed(parser.s)
    if parser.external:
        global extern_list
        extern_list = create_function_list(parser.num_files)

    # pool = mp.Pool(processes=parser.j)
    with open('pynamic.h', 'w') as py_header:
        py_header.write('#include <math.h>\n')
        if parser.num_utility_mods:
            # global utility_list
            # utility_list = []
            for index in range(parser.num_utility_mods):
                py_header.write(f'#include "libutility{index}.h"\n')
                generate_utility_file(index, parser.avg_num_u_functions, parser.name_length, parser.print)
        for index in range(max(1, parser.num_files - parser.num_utility_mods)):
            generate_module_file(parser.num_utility_mods > 0, parser.external, index, parser.avg_num_functions, parser.name_length, parser.print)

def configure(parser):
    if parser.big_exe:
        try:
            os.environ['CFLAGS'] += ' -DBUILD_PYNAMIC_BIGEXE'
        except:
            os.environ['CFLAGS'] = ' -DBUILD_PYNAMIC_BIGEXE'

    if parser.u:
        parser.num_utility_mods, parser.avg_num_u_functions = parser.u

    # configure_args, python_command, bigexe, use_mpi4py, processes = parse_and_run('config_pynamic.py')
    clean_pynamic_files()
    generate_shared_objects(parser)

    pass
    # command = 'make -f Makefile.mpi4py clean'
    # run_command(command)
    #
    # target = 'pynamic-mpi4py'
    # if parser.big_exe == True:
    #     target += ' pynamic-bigexe-mpi4py'
    # command = 'make -j ' + str(processes) + ' -f Makefile.mpi4py ' + target
    # run_command(command)
    #
    # if bigexe == False:
    #     command = 'rm -f pynamic-bigexe-pyMPI pynamic-bigexe-sdb-pyMPI pynamic-bigexe-mpi4py'
    #     run_command(command, False)
    #
    # #
    # # build the addall utility program
    # #
    # if os.path.exists('pynamic-pyMPI-2.6a1/addall.c') != True:
    #     print_error('required file addall.c not found!')
    #     sys.exit(0)
    #
    # command = "gcc -g addall.c -o addall"
    # run_command(command)
    #
    # #
    # # check DBG, text, symbol table, and string table size.
    # #
    # if os.path.exists('pynamic-pyMPI-2.6a1/get-symtab-sizes') != True:
    #     print_error('required file get-symtab-sizes not found!')
    #     sys.exit(0)
    #
    # for exe in ['pynamic-pyMPI', 'pynamic-sdb-pyMPI', 'pynamic-bigexe-pyMPI', 'pynamic-bigexe-sdb-pyMPI', 'pynamic-mpi4py', 'pynamic-bigexe-mpi4py']:
    #     info_file = 'sharedlib_section_info_%s' %(exe)
    #     os.system('rm -f %s' %(info_file))
    #     if os.path.exists(exe):
    #         command = "./get-symtab-sizes %s > %s" %(exe, info_file)
    #         ret = run_command(command)
    #         if ret != 0:
    #             print_error('Failed to get executable statistics for %s!' %(exe))
    #         else:
    #             command = "tail -10 %s" %(info_file)
    #             run_command(command)

if __name__ == '__main__':
    configure(parse_args())
#
#COPYRIGHT
#
#Copyright (c) 2007, The Regents of the University of California.
#Produced at the Lawrence Livermore National Laboratory
#Written by Gregory Lee, Dong Ahn, John Gyllenhaal, Bronis de Supinski.
#UCRL-CODE-228991.
#All rights reserved.
#
#This file is part of Pynamic.   For details contact Greg Lee (lee218@llnl.gov).  Please also read the "ADDITIONAL BSD NOTICE" in pynamic.LICENSE.
#
#Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
#* Redistributions of source code must retain the above copyright notice, this list of conditions and the disclaimer below.
#* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the disclaimer (as noted below) in the documentation and/or other materials provided with the distribution.
#* Neither the name of the UC/LLNL nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OF THE UNIVERSITY OF CALIFORNIA, THE U.S. DEPARTMENT OF ENERGY OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON  ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
