cmake_minimum_required(VERSION 3.10)
project(Pynamic C)

# ==============================================================================
# Configuration Variables
# ==============================================================================

# Default Python executable, can be overridden by user
# e.g., cmake -DPYTHON_EXE=/usr/bin/python3.9 ..
if(NOT DEFINED PYTHON_EXE)
    find_program(PYTHON_EXE NAMES python3 python)
    if(NOT PYTHON_EXE)
        message(FATAL_ERROR "Python executable not found. Please set PYTHON_EXE.")
    endif()
endif()
message(STATUS "Using Python executable: ${PYTHON_EXE}")

# Compiler (MPI C compiler)
# CMake will usually find mpicc if it's in the PATH, or you can set CMAKE_C_COMPILER
find_program(MPI_C_COMPILER mpicc)
if(NOT MPI_C_COMPILER)
    message(FATAL_ERROR "MPI C compiler (mpicc) not found. Please ensure it's in your PATH or set CMAKE_C_COMPILER.")
endif()
set(CMAKE_C_COMPILER ${MPI_C_COMPILER})

# Basic CFLAGS
add_compile_options(-Wall -Wextra -pedantic)

# ==============================================================================
# Python & Pynamic-specific Variables (Derived)
# ==============================================================================

# Find Python development libraries
# This module tries to find all necessary components for embedding Python
find_package(Python 3 COMPONENTS Interpreter Development)
if(NOT Python_FOUND)
    message(FATAL_ERROR "Python 3 development libraries not found. Please ensure Python 3 is installed with development headers.")
endif()

message(STATUS "Python Interpreter: ${Python_EXECUTABLE}")
message(STATUS "Python Includes: ${Python_INCLUDE_DIRS}")
message(STATUS "Python Libraries: ${Python_LIBRARIES}")

# Get the directory where this CMakeLists.txt resides (same as MAKEFILE_DIR)
set(MAKEFILE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")

# Define a macro for C sources to get the ROOT_DIR
add_compile_definitions(ROOT_DIR="${CMAKE_CURRENT_SOURCE_DIR}")

# Automatically discover Pynamic utility and module libraries
# Use file(GLOB) to find .so files in the current source directory
file(GLOB UTIL_LIBS_PATHS "${CMAKE_CURRENT_SOURCE_DIR}/libutility*.so")
file(GLOB MODULE_LIBS_PATHS "${CMAKE_CURRENT_SOURCE_DIR}/libmodule*.so")

# Extract library names from paths and format them for linking
# For example, "/path/to/libutility0.so" -> "utility0"
set(UTIL_LIALIBS "")
foreach(lib_path IN LISTS UTIL_LIBS_PATHS)
    get_filename_component(lib_name "${lib_path}" NAME_WE) # NAME_WE = Name WithOut Extension
    string(REGEX REPLACE "^lib" "" lib_name_cleaned "${lib_name}") # Remove "lib" prefix
    list(APPEND UTIL_LIALIBS "${lib_name_cleaned}")
endforeach()

set(MODULE_LIALIBS "")
foreach(lib_path IN LISTS MODULE_LIBS_PATHS)
    get_filename_component(lib_name "${lib_path}" NAME_WE)
    string(REGEX REPLACE "^lib" "" lib_name_cleaned "${lib_name}")
    list(APPEND MODULE_LIALIBS "${lib_name_cleaned}")
endforeach()

# Explicitly defined base module libraries (assuming they exist as libmodulebegin.so, libmodulefinal.so)
set(BASE_MODULE_LIBS modulebegin modulefinal)

# Add the current source directory as a library search path for custom libraries
link_directories(${CMAKE_CURRENT_SOURCE_DIR})

# ==============================================================================
# Source Files
# ==============================================================================

# Main MPI4PY C source file
set(MAIN_SOURCES mpi4py_main.c)

# "Bigexe" specific C source files
set(BIGEXE_SOURCES foo0.c foo1.c foo2.c foo3.c foo4.c foo5.c foo6.c foo7.c foo8.c foo9.c)

# If fooN.c is a header or an additional source, ensure it's available.
# If it's a source file that needs compiling, add it here.
# Assuming it's a common header for BIGEXE_SOURCES, it's implicitly handled by compilation.
# If it's a separate source, add to BIGEXE_SOURCES:
# list(APPEND BIGEXE_SOURCES fooN.c)

# ==============================================================================
# Executables
# ==============================================================================

# Target: pynamic-mpi4py
add_executable(pynamic-mpi4py ${MAIN_SOURCES})
target_include_directories(pynamic-mpi4py PRIVATE ${Python_INCLUDE_DIRS}) # Add Python includes
target_link_libraries(pynamic-mpi4py
    PRIVATE
        ${Python_LIBRARIES} # Link Python libraries
        ${MODULE_LIALIBS}   # Discovered module libraries
        ${UTIL_LIALIBS}     # Discovered utility libraries
        ${BASE_MODULE_LIBS} # Explicit base module libraries
)

# Target: pynamic-bigexe-mpi4py
add_executable(pynamic-bigexe-mpi4py ${MAIN_SOURCES} ${BIGEXE_SOURCES})
target_compile_definitions(pynamic-bigexe-mpi4py PRIVATE BUILD_PYNAMIC_BIGEXE) # Define for bigexe sources
target_include_directories(pynamic-bigexe-mpi4py PRIVATE ${Python_INCLUDE_DIRS}) # Add Python includes
target_link_libraries(pynamic-bigexe-mpi4py
    PRIVATE
        ${Python_LIBRARIES} # Link Python libraries
        ${MODULE_LIALIBS}   # Discovered module libraries
        ${UTIL_LIALIBS}     # Discovered utility libraries
        ${BASE_MODULE_LIBS} # Explicit base module libraries
)

# ==============================================================================
# Custom Targets (Optional, for building modules/utilities if they are also
# part of this project. Assuming they are pre-built .so files here.)
# ==============================================================================

# If you also want CMake to build libutilityX.so, libmoduleX.so, libmodulebegin.so, etc.,
# you would add `add_library()` commands here for each.
# For example:
# add_library(utility0 SHARED libutility0.c)
# target_include_directories(utility0 PUBLIC ...)
# target_link_libraries(utility0 PUBLIC ...)
#
# But based on your Makefile, these seem to be pre-existing .so files that are linked against.