#! /usr/bin/env python

import sys
import os
import argparse
from pathlib import Path
import random
import multiprocessing as mp
import subprocess

class PositiveInt(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values < 0:
            parser.error(f"{option_string or values} must be a positive integer.")
        setattr(namespace, self.dest, int(values))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate Pynamic shared libraries and configure/build', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("num_files", type=int, action=PositiveInt, help="Total number of shared objects to produce")
    parser.add_argument("avg_num_functions", type=int, action=PositiveInt, help="Average number of functions per shared object")

    parser.add_argument("-b", "--big-exe", action="store_true",
                        help="Generate the pynamic-bigexe-pyMPI and pynamic-bigexe-sdb-pyMPI executables")

    parser.add_argument("-d","--depth", type=int, default=10, action=PositiveInt,
                        help="Maximum Pynamic call stack depth")

    parser.add_argument("-e","--external", action="store_true",
                        help="Enable external functions to call across modules")

    parser.add_argument("-i", "--include", metavar="python_include_dir",
                        help="Add <python_include_dir> when compiling modules")

    parser.add_argument("-j","--jobs", metavar="[N]", type=int, action=PositiveInt,
                        help="Build in parallel with a max of <N> processes")

    parser.add_argument("-n", dest="name_length", default=0, metavar="[N]", type=int, action=PositiveInt,
                        help="Add <N> characters to the function names")

    parser.add_argument("-p", "--print", action="store_true",
                        help="Add a print statement to every generated function")

    parser.add_argument("-s", "--seed", type=int,
                        help="Seed to the random number generator")

    parser.add_argument("-u", nargs=2, type=int, default=(0,0), metavar=('num_utility_mods', 'avg_num_u_functions'),
                        help="Create utility modules with an average number of functions")

    parser.add_argument("-G", "--generator", type=str, default="Unix Makefiles", help="Compile C Modules with <G> generator. (Ninja runs faster)")

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
    top_dir = Path('./gen_src')
    if not top_dir.exists():
        top_dir.mkdir()
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

def create_function_declaration(function_name, function_signature) -> str:
    # Signature is of the form [return_type, num_args, arg_type1, arg_type2, ...]
    return_type = function_signature[0]
    arg_types = function_signature[2:]

    args_str = ", ".join(f"{arg_type} arg{i}" for i, arg_type in enumerate(arg_types))

    return f"{return_type:4}\t{function_name}({args_str})"

def create_function_call(function_name, function_signature)-> str:
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

def generate_function_names(base_name: str, avg_num_functions: int, name_length: int) -> list:
    """
    Args:
        base_name: Prefix for function names.
        avg_num_functions: Number of Functions returned
        name_length: Number of digits appended to function name

    Returns:
        List of function names and signatures.
    """
    num_functions = random.randint(avg_num_functions // 2, (avg_num_functions * 3) // 2)
    signatures = create_function_list(num_functions)
    digits = "0123456789"
    output = []
    for idx, signature in enumerate(signatures):
        suffix = ''.join(random.choices(digits, k=name_length)) if name_length else ''
        output.append((f"{base_name}_fun{idx}{suffix}", signature))

    return output

def run_command(command):
    try:
        subprocess.run(command, shell=False, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"{command} | {e}")
        sys.exit(1)

def configure_and_build_libraries(generator: str, source_dir ="gen_src", build_dir ="build", jobs: int = 1, python_dir=None):
    clean_command = [
        'rm',
        '-rf',
        str(build_dir),
    ]

    cfg_command = [
        'cmake',
        f'-G', generator,
        f'-B', str(build_dir),
        f'-DPython_ROOT_DIR={python_dir}' if python_dir else "",
    ]
    build_command = [
        'cmake',
        '--build',
        str(build_dir),
        '-j', str(jobs),
    ]
    run_command(clean_command)
    run_command(cfg_command)
    run_command(build_command)


class Pynamic:
    def __init__(self, parser: argparse.Namespace):
        if parser.seed:
            random.seed(parser.seed)
        if parser.big_exe:
            try:
                os.environ['CFLAGS'] += ' -DBUILD_PYNAMIC_BIGEXE'
            except:
                os.environ['CFLAGS'] = ' -DBUILD_PYNAMIC_BIGEXE'
        self.num_module_files: int = parser.num_files
        self.avg_num_functions: int = parser.avg_num_functions
        if parser.u:
            self.num_util_files, self.avg_num_u_functions = parser.u
        self.module_file_count: int = max(1, self.num_module_files - self.num_util_files)
        self.utility_list = []
        self.extern_list = []
        if parser.external:
            self.extern_list = create_function_list(self.num_module_files)
        self.print_verbose: bool = parser.print
        self.name_length: int = parser.name_length
        self.cmake_generator: str = parser.generator
        self.job_count: int = parser.jobs if parser.jobs else 1
        self.python_dir = parser.include

    def generate_library_header(self):
        with open('gen_src/pynamic.h', 'w') as py_header:
            py_header.write('#include <math.h>\n')
            for index in range(self.num_util_files):
                py_header.write(f'#include "libutility{index}.h"\n')
            py_header.write("void initlibmodulebegin();\n")
            for index in range(self.module_file_count):
                py_header.write(f"void initlibmodule{index}();\n")
            py_header.write("void initlibmodulefinal();\n")

    def generate_utility_file(self, identity: int):
        filename = 'libutility' + str(identity)
        utility_list = generate_function_names(filename, self.avg_num_u_functions, self.name_length)

        header_content = []
        c_content = []

        # Generate the Header file and Function declarations
        header_content.append('#include <stdio.h>\n#include <stdlib.h>\n\n')
        for func_name, signature in utility_list:
            header_content.append(create_function_declaration(func_name, signature) + ';\n')

        # Generate the C File content
        c_content.append('#include "' + filename + '.h"\n\n')
        for index, (func_name, signature) in enumerate(utility_list):
            c_content.append(create_function_declaration(func_name, signature) + ' {\n')
            c_content.append('\t' + signature[0] + ' ret_val;\n')
            c_content.append(
                "\tint a, b, c, loop;\n"
                "\tfloat d = 0.0, e = 1.0, f = 2.0;\n"
                "\tdouble g = 0.0, h = 3.0, i = 4.0;\n"
                "\tchar j[10], k[100], l[10][10];\n\n"
            )

            if self.print_verbose:
                c_content.append('\tprintf("In module ' + filename + ' function ' + func_name + '\\n");\n')
            c_content.append(
                "\tfor (loop = 0; loop < 10; loop++)\n"
                "\t{\n"
                "\t\ta = loop;\n"
                "\t}\n"
            )

            if index != len(utility_list) - 1:
                f_call = create_function_call(utility_list[index + 1][0], utility_list[index + 1][1])
                c_content.append('\t' + f_call + ';\n')
            c_content.append('\treturn ret_val;\n}\n\n')

        with open("gen_src/" + filename + '.h', 'w') as h_file:
            h_file.writelines(header_content)
        with open("gen_src/" + filename + '.c', 'w') as c_file:
            c_file.writelines(c_content)

        self.utility_list.append(utility_list)

    def generate_module_file(self, identity: int, call_depth: int = 10):
        filename = 'libmodule' + str(identity)
        module_functions_list = generate_function_names(filename, self.avg_num_functions, self.name_length)
        c_content = []

        c_content.append('#include <Python.h>\n')
        if self.utility_list:
            c_content.append('#include "pynamic.h"\n')
        c_content.append("\n")
        if self.extern_list:
            if identity != 0:
                c_content.append('extern ')
                decl = create_function_declaration( f"libmodule{identity -1}_extern", self.extern_list[identity - 1] )
                c_content.append(decl + ";\n")
            c_content.append(create_function_declaration(filename + "_extern", self.extern_list[identity]))
            c_content.append(f"\n{{\n\t{self.extern_list[identity][0]} ret_val;")
            if self.print_verbose:
                c_content.append(f"\tprintf(\"I am {filename}_extern called from another module\\n\");\n")
            c_content.append('\treturn ret_val;\n}\n\n')

        # Create Function Declarations
        for func_name, signature in module_functions_list:
            c_content.append(create_function_declaration(func_name, signature) + ";\n")
        c_content.append("\n")

        # Create Function Definitions
        for index, (func_name, signature) in enumerate(module_functions_list):
            c_content.append(create_function_declaration(func_name, signature) + "{\n")
            c_content.append('\t' + signature[0] + ' ret_val;\n')
            c_content.append(
                "\tint a, b, c, loop;\n"
                "\tfloat d = 0.0, e = 1.0, f = 2.0;\n"
                "\tdouble g = 0.0, h = 3.0, i = 4.0;\n"
                "\tchar j[10], k[100], l[10][10];\n\n"
            )
            if self.print_verbose:
                c_content.append('\tprintf("In module ' + filename + ' function ' + func_name + '\\n");\n')
            c_content.append(
                "\tfor (loop = 0; loop < 10; loop++)\n"
                "\t{\n"
                "\t\ta = loop;\n"
            )

            if self.utility_list:
                utility_file = random.choice(self.utility_list)
                func_name, signature = random.choice(utility_file)
                utility_call = create_function_call( func_name, signature )
                c_content.append("\t\t" + utility_call)
            c_content.append("\n\t}\n")

            if index != len(module_functions_list) - 1:
                f_call = create_function_call(module_functions_list[index + 1][0], module_functions_list[index + 1][1])
                c_content.append(f"\t{f_call}\n")
            c_content.append('\treturn ret_val;\n}\n\n')

        # Create PyObject Entry
        entry_func_name = filename + "_entry"
        c_content.append(f"static PyObject *py_{entry_func_name}(PyObject *self, PyObject *args){{\n")
        c_content.append("\tint ret_val = 0;\n")

        for index, (func_name, signature) in enumerate(module_functions_list):
            if index % call_depth == 0:
                func_call = create_function_call( func_name, signature )
                c_content.append(f"\t{func_call}\n")

        if identity != 0 and self.extern_list:
            func_call = create_function_call( f"libmodule{identity - 1}_extern", self.extern_list[identity - 1] )
            c_content.append(f"\t{func_call}\n")
        c_content.append("\treturn Py_BuildValue(\"i\", ret_val);\n}\n\n")

        # Initialize Python CModule
        c_content.append(f"static PyMethodDef {filename}Methods[] = {{\n")
        c_content.append(f"\t{{\"{entry_func_name}\", py_{entry_func_name}, METH_VARARGS, \"a function.\"}},\n")
        c_content.append("\t{NULL, NULL, 0, NULL}\n};\n\n")

        c_content.append(f"PyMODINIT_FUNC PyInit_{filename}(){{\n")
        c_content.append(
            "\tstatic struct PyModuleDef mod = {\n"
            "\t\tPyModuleDef_HEAD_INIT,\n"
        )
        c_content.append(f"\t\t\"{filename}\",\n")
        c_content.append("\t\t\"\",\n\t\t-1,\n")
        c_content.append(f"\t\t{filename}Methods\n\t}};\n")
        c_content.append("\treturn PyModule_Create(&mod);\n}\n\n")

        with open("gen_src/" + filename + '.c', 'w') as c_file:
            c_file.writelines(c_content)

    def generate_driver_file(self):
        with open("templates/pynamic_driver_mpi4py.py", "r") as f:
            lines = f.readlines()

        updated_lines = []
        in_import_block = False
        in_call_block = False

        for line in lines:
            if line.strip() == '## START_MODULE_IMPORTS':
                updated_lines.append(line)
                in_import_block = True

                for i in range(self.module_file_count):
                    updated_lines.append(f'import libmodule{i}\n')
                continue  # Skip adding the original line, as we've replaced the block

            if line.strip() == '## END_MODULE_IMPORTS':
                in_import_block = False
                updated_lines.append(line)  # Add the end marker
                continue

            if line.strip() == '## START_MODULE_CALLS':
                updated_lines.append(line)
                in_call_block = True
                # Insert new call lines
                for i in range(self.module_file_count):
                    updated_lines.append(f'libmodule{i}.libmodule{i}_entry()\n')
                continue  # Skip adding the original line, as we've replaced the block

            if line.strip() == '## END_MODULE_CALLS':
                in_call_block = False
                updated_lines.append(line)  # Add the end marker
                continue

            # If we are inside a marked block, skip the original lines
            if in_import_block or in_call_block:
                continue

            updated_lines.append(line)

        with open("gen_src/pynamic_driver_mpi4py.py", "w") as f:
            f.writelines(updated_lines)

    def configure(self):
        print("Cleaning old files...")
        clean_pynamic_files()

        print("Generating Library Header")
        self.generate_library_header()

        if self.num_util_files:
            print("Generating Utility Libraries...")
            for index in range(self.num_util_files):
                self.generate_utility_file(index)

        print(f"Generating {self.module_file_count} Modules {'using ' + str(self.job_count) + ' jobs' if self.job_count > 1 else ''}...")
        with mp.Pool(processes=self.job_count) as pool:
            pool.map(self.generate_module_file, range(self.module_file_count))

        print('Generating driver')
        self.generate_driver_file()

        print('Building libraries')
        configure_and_build_libraries(generator=self.cmake_generator, jobs=self.job_count, python_dir=self.python_dir)
        print('Done!\n')


if __name__ == '__main__':
    configurator = Pynamic(parse_args())
    configurator.configure()
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
