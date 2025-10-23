cmake_minimum_required(VERSION 3.10)
project(PynamicSharedLibrary C)

find_package(Python 3 COMPONENTS Interpreter Development)
if(Python_FOUND)
    message(STATUS "Found Python3: ${Python_EXECUTABLE}")
    message(STATUS "Python3 include directories: ${Python_INCLUDE_DIRS}")
    # Add Python's include directories to your project
    include_directories(${Python_INCLUDE_DIRS})
    # If you're linking against the Python library later, you'd also use ${Python3_LIBRARIES}
else()
    message(FATAL_ERROR "Python 3 development libraries not found. Please ensure Python 3 is installed with development headers.")
endif()

# Define a variable to hold the list of source files
set(UTILITY_SOURCES "")
set(MODULE_SOURCES "")

file(GLOB UTILITY_SOURCES "libutility*.c")
file(GLOB MODULE_SOURCES "libmodule*.c")
set(MODULE_STATIC_SOURCES "libmodulefinal.c" "libmodulebegin.c")

# Check if any files were found
if(NOT MODULE_SOURCES)
    message(FATAL_ERROR "No libmodule*.c files found in ${CMAKE_CURRENT_SOURCE_DIR}")
endif()

# Get the count of detected files (optional, for informational purposes)
list(LENGTH UTILITY_SOURCES NUM_U_FILES)
list(LENGTH MODULE_SOURCES NUM_M_FILES)
message(STATUS "Detected ${NUM_U_FILES} module files.")
message(STATUS "Detected ${NUM_M_FILES} utility files.")

# --- THE KEY CHANGE IS HERE: Use SHARED instead of STATIC ---
# Add the shared library target
if (NUM_U_FILES GREATER 0)
    add_library(utility SHARED ${UTILITY_SOURCES})
endif()

add_library(modules SHARED ${MODULE_SOURCES})
target_include_directories(modules PRIVATE ${Python_INCLUDE_DIRS})
target_link_libraries(modules PRIVATE ${Python_LIBRARIES})

add_library(pynamic STATIC ${UTILITY_SOURCES} ${MODULE_SOURCES} ${MODULE_STATIC_SOURCES})
