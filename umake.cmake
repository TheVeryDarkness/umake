# Under MIT License, see ./License

# For ADDITIONAL_CLEAN_FILES
cmake_minimum_required(VERSION 3.15)

if(NOT ${CMAKE_GENERATOR} STREQUAL "Ninja")
    message("Errors may occur if using \"${CMAKE_GENERATOR}\" as generator. I'm trying to fix them, but Ninja should work for you.")
endif()

include(CheckCXXCompilerFlag)
set(CXX_DEFINITION_HEAD -D)
set(CXX_PRECOMPILED_MODULES_DIR ${CMAKE_CURRENT_BINARY_DIR}/.cppm)
if(MSVC)
    # See https://docs.microsoft.com/en-us/cpp/preprocessor/predefined-macros
    # See https://docs.microsoft.com/en-us/cpp/error-messages/compiler-warnings/c5050
    # I don't know whether there is a possibility that one doesn't add "/EHsc".
    # MT, or MD, that's a question
    set(CXX_MODULES_FOR_CHECK /experimental:module)
    set(CXX_MODULES_FLAGS /nologo /experimental:module /std:c++20)
    set(CXX_PRECOMPILED_MODULES_EXT ifc)
    set(CXX_MODULES_CREATE_FLAGS -c)

    if(MSVC_VERSION LESS 1928)
        list(APPEND CXX_MODULES_FLAGS /module:interface)
        set(CXX_MODULES_REFERENCE_FLAG /module:reference)
        set(CXX_MODULES_OUTPUT_FLAG /module:output)
    else()
        list(APPEND CXX_MODULES_FLAGS /interface)
        set(CXX_MODULES_REFERENCE_FLAG /reference)
        set(CXX_MODULES_OUTPUT_FLAG /ifcOutput)
    endif()
else() # Any more check?
    set(CXX_MODULES_FOR_CHECK -fmodules)
    set(CXX_MODULES_FLAGS -fmodules -std=c++20)
    set(CXX_PRECOMPILED_MODULES_EXT pcm)
    set(CXX_MODULES_CREATE_FLAGS -fmodules -x c++-module --precompile)
    set(CXX_MODULES_REFERENCE_FLAG -fmodule-file=)
    set(CXX_MODULES_OUTPUT_FLAG -o)
endif()

# Check if c++ compiler supports c++ modules.
# Otherwise raise a fatal error.
check_cxx_compiler_flag(${CXX_MODULES_FOR_CHECK} CXX_MODULES_SUPPORTED)
if (NOT CXX_MODULES_SUPPORTED)
    message(FATAL_ERROR "Compiler \"${CMAKE_CXXCOMPILER_ID}\" doesn't support C++ 20 modules. Checked by flag \"${CXX_MODULES_FOR_CHECK}\"")
endif ()

# Add flags to the target to enable module support.
function (target_enable_cxx_modules TARGET)
    target_compile_options(${TARGET} PRIVATE ${CXX_MODULES_FLAGS})
endfunction ()

# Add module dependencies to the target
function(target_add_module_dependencies ESCAPED_TARGET ESCAPED_REFERENCE)
    target_link_libraries(${ESCAPED_TARGET} PRIVATE ${ESCAPED_REFERENCE})
    add_dependencies(${ESCAPED_TARGET} ${ESCAPED_REFERENCE})
endfunction()

function(add_object_dependency SOURCE REFERENCE)
    get_target_property(INTERFACE_FILE ${REFERENCE} CXX_MODULE_INTERFACE_FILE)
    get_source_file_property(INTERFACE_DEPENDS ${SOURCE} OBJECT_DEPENDS)

    set(NEW_OBJECT_DEPEND "${CMAKE_CURRENT_BINARY_DIR}/CMakeFiles/${REFERENCE}.dir/${INTERFACE_FILE}${CMAKE_CXX_OUTPUT_EXTENSION}")

    if(NOT INTERFACE_DEPENDS)
        set(INTERFACE_DEPENDS ${NEW_OBJECT_DEPEND})
    else()
        string(APPEND INTERFACE_DEPENDS ";${NEW_OBJECT_DEPEND}")
    endif()
    set_property(SOURCE ${SOURCE} PROPERTY OBJECT_DEPENDS ${INTERFACE_DEPENDS})
endfunction()

## Create C++ module interface.
## add_module_library(TARGET SOURCE <SOURCE> [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
## Set target property below:
##  CXX_MODULE_NAME             Unescaped module name
##  CXX_MODULE_INTERFACE_FILE   Source file path
##  CXX_MODULE_REFERENCES       Escaped names of referenced modules
function (add_module_library TARGET _SOURCE SOURCE)
    # Set cmake to use CXX compiler on C++ module files
    set_source_files_properties(${SOURCE} PROPERTIES LANGUAGE CXX)

    string(REPLACE ":" ".." ESCAPED_TARGET ${TARGET})

    set(REFERENCES ${ARGN})
    if(REFERENCES)
        list(POP_FRONT REFERENCES _REFERENCE)
        if(NOT ${_REFERENCE} STREQUAL REFERENCE)
            message(FATAL_ERROR "\"${_REFERENCE}\" should be \"REFERENCE\"")
        endif()
    endif()

    # Create targets for interface files
    if(IS_ABSOLUTE ${SOURCE})
        file(RELATIVE_PATH SOURCE ${CMAKE_CURRENT_SOURCE_DIR} ${SOURCE})
    endif()
    set(OUT_FILE ${CXX_PRECOMPILED_MODULES_DIR}/${SOURCE}.${CXX_PRECOMPILED_MODULES_EXT})
    set(IN_FILE ${CMAKE_CURRENT_SOURCE_DIR}/${SOURCE})

    # Make directory for pre-compiled modules
    get_filename_component(OUT_FILE_DIR ${OUT_FILE} DIRECTORY)

    if (OUT_FILE_DIR)
        file(MAKE_DIRECTORY ${OUT_FILE_DIR})
    endif()

    # Create interface build target
    add_library(${ESCAPED_TARGET} OBJECT ${SOURCE})

    # Store property with interface file
    set_target_properties(${ESCAPED_TARGET}
        PROPERTIES
        CXX_MODULE_NAME "${TARGET}"
        CXX_MODULE_INTERFACE_FILE "${SOURCE}"
        CXX_MODULE_REFERENCES "${REFERENCES}"
    )
    set(ESCAPED_REFERENCES)
    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        target_add_module_dependencies(${ESCAPED_TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${ESCAPED_TARGET}
            PRIVATE "SHELL:${CXX_MODULES_REFERENCE_FLAG} ${MODULENAME}=${CXX_PRECOMPILED_MODULES_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
        add_object_dependency(${SOURCE} ${ESCAPED_REFERENCE})
    endforeach ()
    target_compile_options(${ESCAPED_TARGET} PRIVATE ${CXX_MODULES_FLAGS} ${CXX_MODULES_OUTPUT_FLAG} "${OUT_FILE}")

    get_property(_CLEAN_FILES TARGET ${ESCAPED_TARGET} PROPERTY ADDITIONAL_CLEAN_FILES)
    if(NOT ${_CLEAN_FILES})
        set(_CLEAN_FILES ${OUT_FILE})
    else()
        string(APPEND _CLEAN_FILES ${OUT_FILE})
    endif()
    set_property(TARGET ${ESCAPED_TARGET} PROPERTY ADDITIONAL_CLEAN_FILES ${_CLEAN_FILES})
endfunction ()

## Link a (C++ module) library to (C++ module) target.
##  add_moduled_executable(TARGET SOURCE <SOURCE> [DEPENDS <DEPEND1> [<DEPEND2> ...]] [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
##  Both DEPEND and REFERENCE are target names
function (add_moduled_executable TARGET)
    if(NOT ${_SOURCE} STREQUAL SOURCE)
        message(FATAL_ERROR "\"${_SOURCE}\" should be \"SOURCE\"")
    endif()

    set(SOURCES)
    set(DEPENDS)
    set(REFERENCES)
    set(MODE SOURCE)
    foreach(TOKEN IN LISTS ARGN)
        if(${TOKEN} STREQUAL SOURCE)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL DEPEND)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL REFERENCE)
            set(MODE ${TOKEN})
        else()
            list(APPEND ${MODE}S ${TOKEN})
        endif()
    endforeach()

    # Enable modules for target
    add_executable(${TARGET})
    target_sources(${TARGET} PRIVATE ${SOURCES})
    target_enable_cxx_modules(${TARGET})

    add_dependencies(${TARGET} ${DEPENDS})
    target_link_libraries(${TARGET} PRIVATE ${DEPENDS})

    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        target_add_module_dependencies(${TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${TARGET}
            PRIVATE "SHELL:${CXX_MODULES_REFERENCE_FLAG} ${MODULENAME}=${CXX_PRECOMPILED_MODULES_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
        foreach(SOURCE IN LISTS SOURCES)
            add_object_dependency(${SOURCE} ${ESCAPED_REFERENCE})
        endforeach()
    endforeach ()
endfunction ()

## Link a (C++ module) library to (C++ module) target.
##  add_moduled_executable(TARGET SOURCE <SOURCE> [DEPENDS <DEPEND1> [<DEPEND2> ...]] [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
##  Both DEPEND and REFERENCE are target names
function (add_moduled_library TARGET)
    if(NOT ${_SOURCE} STREQUAL SOURCE)
        message(FATAL_ERROR "\"${_SOURCE}\" should be \"SOURCE\"")
    endif()

    set(SOURCES)
    set(DEPENDS)
    set(REFERENCES)
    set(MODE SOURCE)
    set(TYPE)
    foreach(TOKEN IN LISTS ARGN)
        if(${TOKEN} STREQUAL STATIC)
            set(TYPE ${TOKEN})
        elseif(${TOKEN} STREQUAL SHARED)
            set(TYPE ${TOKEN})
        elseif(${TOKEN} STREQUAL MODULE)
            set(TYPE ${TOKEN})
        elseif(${TOKEN} STREQUAL OBJECT)
            set(TYPE ${TOKEN})
        elseif(${TOKEN} STREQUAL SOURCE)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL DEPEND)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL REFERENCE)
            set(MODE ${TOKEN})
        else()
            list(APPEND ${MODE}S ${TOKEN})
        endif()
    endforeach()

    # Enable modules for target
    add_library(${TARGET} ${TYPE})
    target_sources(${TARGET} PRIVATE ${SOURCES})
    target_enable_cxx_modules(${TARGET})

    add_dependencies(${TARGET} ${DEPENDS})
    target_link_libraries(${TARGET} PRIVATE ${DEPENDS})

    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        target_add_module_dependencies(${TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${TARGET}
            PRIVATE "SHELL:${CXX_MODULES_REFERENCE_FLAG} ${MODULENAME}=${CXX_PRECOMPILED_MODULES_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
        foreach(SOURCE IN LISTS SOURCES)
            add_object_dependency(${SOURCE} ${ESCAPED_REFERENCE})
        endforeach()
    endforeach ()
endfunction ()

## Create static libraries that correspond to single source file.
##  add_source_file_target(TARGET SOURCE <SOURCE> [DEPENDS <DEPEND1> [<DEPEND2> ...]] [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
##  Both DEPEND and REFERENCE are target names
function(add_source_file_target TARGET)
    if(NOT ${_SOURCE} STREQUAL SOURCE)
        message(FATAL_ERROR "\"${_SOURCE}\" should be \"SOURCE\"")
    endif()

    set(SOURCES)
    set(DEPENDS)
    set(REFERENCES)
    set(MODE SOURCES)
    foreach(TOKEN IN LISTS ARGN)
        if(${TOKEN} STREQUAL SOURCE)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL DEPEND)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL REFERENCE)
            set(MODE ${TOKEN})
        else()
            list(APPEND ${MODE}S ${TOKEN})
        endif()
    endforeach()

    # Enable modules for target
    add_library(${TARGET} STATIC ${SOURCES})
    target_enable_cxx_modules(${TARGET})

    target_link_libraries(${TARGET} PRIVATE ${DEPENDS})

    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        target_add_module_dependencies(${TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${TARGET}
            PRIVATE "SHELL:${CXX_MODULES_REFERENCE_FLAG} ${MODULENAME}=${CXX_PRECOMPILED_MODULES_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
        foreach(SOURCE IN LISTS SOURCES)
            add_object_dependency(${SOURCE} ${ESCAPED_REFERENCE})
        endforeach()
    endforeach ()
endfunction()

function(execute_umake_command_for_executable command)
    # Run "cmake --help-policy CMP0054" for help
    cmake_policy(SET CMP0054 NEW)
    string(REPLACE "\\" "/" command ${command})
    string(REGEX MATCHALL "[0-9/:._a-zA-Z-]+" cmds "${command}")
    list(POP_FRONT cmds head)
    if("MODULE" STREQUAL ${head})
        add_module_library(${cmds})
    elseif("TARGET" STREQUAL ${head})
        add_moduled_executable(${cmds})
    elseif("OBJECT" STREQUAL ${head})
        add_source_file_target(${cmds})
    else()
        message(FATAL_ERROR "Failed to parse the result of umake. \"${head}\" is not a correct target type.")
    endif()
endfunction()

function(execute_umake_command_for_library command)
    # Run "cmake --help-policy CMP0054" for help
    cmake_policy(SET CMP0054 NEW)
    string(REPLACE "\\" "/" command ${command})
    string(REGEX MATCHALL "[0-9/:._a-zA-Z-]+" cmds "${command}")
    list(POP_FRONT cmds head)
    if("MODULE" STREQUAL ${head})
        add_module_library(${cmds})
    elseif("TARGET" STREQUAL ${head})
        add_moduled_library(${cmds})
    elseif("OBJECT" STREQUAL ${head})
        add_source_file_target(${cmds})
    else()
        message(FATAL_ERROR "Failed to parse the result of umake. \"${head}\" is not a correct target type.")
    endif()
endfunction()

function(EXECUTE_UMAKE_PY_FOR_DEPENDENCIES OUT)
    # Check if ARGC is odd.
    # Odd ARGC means path to umake.py is specified
    math(EXPR ODD "(${ARGC}-1)%2")
    if(ODD)
        list(POP_FRONT ARGN UMAKE_PATH)
    else()
        if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/umakeConfig.json")
            file(STRINGS "umakeConfig.json" configJSON)
            string(JSON UMAKE_PATH GET ${configJSON} "umake.py")
        else()
            message(FATAL_ERROR "Configuration does not exist, please specify the path to umake.py.")
        endif()
    endif()
    execute_process(
        COMMAND python ${UMAKE_PATH} --load-config --save-config --root ${CMAKE_CURRENT_LIST_DIR} --target cmake ${ARGN}
        OUTPUT_VARIABLE RESULT
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    )
    set(${OUT} ${RESULT} PARENT_SCOPE)
endfunction()

# add_moduled_executable_with_a_main_source_file([UMAKE_PATH] [<TARGET_NAME1> <SOURCE1> [<TARGET_NAME2> <SOURCE2>]...])
function(add_moduled_executables_with_a_main_source)
    EXECUTE_UMAKE_PY_FOR_DEPENDENCIES(RESULT ${ARGN})
    foreach(cmd IN LISTS RESULT)
        execute_umake_command_for_executable(${cmd})
    endforeach(cmd)
endfunction()

# add_moduled_library_with_a_main_source_file([UMAKE_PATH] [<TARGET_NAME1> <SOURCE1> [<TARGET_NAME2> <SOURCE2>]...])
function(add_moduled_library_with_a_main_source)
    set(TYPE)
    list(FIND ARGN STATIC MODE_INDEX)
    if(${MODE_INDEX} GREATER_EQUAL 0)
        set(TYPE STATIC)
        list(REMOVE_AT ARGN ${MODE_INDEX})
    endif()
    list(FIND ARGN SHARED MODE_INDEX)
    if(${MODE_INDEX} GREATER_EQUAL 0)
        set(TYPE SHARED)
        list(REMOVE_AT ARGN ${MODE_INDEX})
    endif()
    list(FIND ARGN MODULE MODE_INDEX)
    if(${MODE_INDEX} GREATER_EQUAL 0)
        set(TYPE MODULE)
        list(REMOVE_AT ARGN ${MODE_INDEX})
    endif()
    list(FIND ARGN OBJECT MODE_INDEX)
    if(${MODE_INDEX} GREATER_EQUAL 0)
        set(TYPE OBJECT)
        list(REMOVE_AT ARGN ${MODE_INDEX})
    endif()

    EXECUTE_UMAKE_PY_FOR_DEPENDENCIES(RESULT ${ARGN})
    foreach(cmd IN LISTS RESULT)
        execute_umake_command_for_library(${cmd} ${TYPE})
    endforeach(cmd)
endfunction()