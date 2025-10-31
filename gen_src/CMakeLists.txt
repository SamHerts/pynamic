cmake_minimum_required(VERSION 3.10)
project(PynamicSharedLibrary C)

set(CMAKE_SHARED_MODULE_SUFFIX ".so")
set(CMAKE_SHARED_MODULE_PREFIX "")

find_package(Python 3 COMPONENTS Interpreter Development)
if(Python_FOUND)
    message(STATUS "Found Python3: ${Python_EXECUTABLE}")
    message(STATUS "Python3 include directories: ${Python_INCLUDE_DIRS}")
    include_directories(${Python_INCLUDE_DIRS})
else()
    message(FATAL_ERROR "Python 3 development libraries not found. Please ensure Python 3 is installed with development headers.")
endif()

find_package(MPI COMPONENTS C)
if(MPI_FOUND)
    message(STATUS "Found MPI - ${MPI_VERSION}")
    message(STATUS "MPI include directores: ${MPI_C_INCLUDE_DIRS}")
    include_directories(${MPI_C_INCLUDE_DIRS})
else()
        message(FATAL_ERROR "MPI library not found. Please ensure MPI is installed.")
endif()

set(UTILITY_SOURCES "")
set(MODULE_SOURCES "")

file(GLOB UTILITY_SOURCES "libutility*.c")
file(GLOB MODULE_SOURCES "libmodule*.c")
set(MODULE_STATIC_SOURCES "libmodulefinal.c" "libmodulebegin.c")

# Check if any files were found
if(NOT MODULE_SOURCES)
    message(FATAL_ERROR "No libmodule*.c files found in ${CMAKE_CURRENT_SOURCE_DIR}")
endif()

# Get the count of detected files
list(LENGTH UTILITY_SOURCES NUM_U_FILES)
list(LENGTH MODULE_SOURCES NUM_M_FILES)
message(STATUS "Detected ${NUM_U_FILES} module files.")
message(STATUS "Detected ${NUM_M_FILES} utility files.")

set(UTILITY_TARGETS "")

if (NUM_U_FILES GREATER 0)
    foreach(UTILITY_FILE ${UTILITY_SOURCES})
        get_filename_component(UTILITY_NAME ${UTILITY_FILE} NAME_WE)
        add_library(${UTILITY_NAME} SHARED ${UTILITY_FILE})
        target_include_directories(${UTILITY_NAME} PRIVATE ${Python_INCLUDE_DIRS})
        target_link_libraries(${UTILITY_NAME} PRIVATE Python::Python)
        list(APPEND UTILITY_TARGETS ${UTILITY_NAME})
    endforeach()
endif()

add_library(pynamic_interface INTERFACE)
target_link_libraries(pynamic_interface INTERFACE Python::Python MPI::MPI_C)
target_include_directories(pynamic_interface INTERFACE ${Python_INCLUDE_DIRS} ${MPI_C_INCLUDE_DIRS})

foreach(MODULE_FILE ${MODULE_SOURCES})
    get_filename_component(MODULE_NAME ${MODULE_FILE} NAME_WE)

    # Create a Python extension module
    add_library(${MODULE_NAME} MODULE ${MODULE_FILE})
    target_link_libraries(${MODULE_NAME} PRIVATE pynamic_interface ${UTILITY_TARGETS})
endforeach()

add_library(pynamic STATIC ${UTILITY_SOURCES} ${MODULE_SOURCES} ${MODULE_STATIC_SOURCES})

set(MAIN_SOURCES "mpi4py_main.c")

add_executable(pynamic-mpi4py ${MAIN_SOURCES})
target_compile_definitions(pynamic-mpi4py PRIVATE ROOT_DIR=${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(pynamic-mpi4py pynamic MPI::MPI_C Python::Python)

add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/pynamic_driver_mpi4py.py
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${CMAKE_CURRENT_SOURCE_DIR}/pynamic_driver_mpi4py.py
            ${CMAKE_CURRENT_BINARY_DIR}/pynamic_driver_mpi4py.py
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/pynamic_driver_mpi4py.py
    COMMENT "Copying pynamic_driver_mpi4py.py to build directory"
)

add_custom_target(copy_driver ALL
    DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/pynamic_driver_mpi4py.py
)

add_dependencies(pynamic-mpi4py copy_driver)

