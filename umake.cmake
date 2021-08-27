# Under MIT License, see ./License
cmake_minimum_required(VERSION 3.0)

include(CheckCXXCompilerFlag)
set(CXX_DEFINITION_HEAD -D)
if(MSVC)
    if(MSVC_VERSION LESS 1928)
        set(CXX_MODULES_FOR_CHECK /experimental:module)
        set(CXX_MODULES_FLAGS /experimental:module /module:interface)
        set(CXX_PRECOMPILED_MODULES_EXT ifc)
        set(CXX_MODULES_CREATE_FLAGS -c)
        set(CXX_MODULES_USE_FLAG /module:reference)
        set(CXX_MODULES_OUTPUT_FLAG /module:output)
    else()
        set(CXX_MODULES_FOR_CHECK /experimental:module)
        set(CXX_MODULES_FLAGS /nologo /experimental:module /std:c++20 /interface)
        set(CXX_PRECOMPILED_MODULES_EXT ifc)
        set(CXX_MODULES_CREATE_FLAGS -c)
        set(CXX_MODULES_USE_FLAG /reference)
        set(CXX_MODULES_OUTPUT_FLAG /ifcOutput)
    endif()
else() # Any more check?
    set(CXX_MODULES_FOR_CHECK -fmodules)
    set(CXX_MODULES_FLAGS -fmodules -std=c++20)
    set(CXX_PRECOMPILED_MODULES_EXT pcm)
    set(CXX_MODULES_CREATE_FLAGS -fmodules-ts -x c++-module --precompile)
    set(CXX_MODULES_USE_FLAG -fmodule-file=)
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

# Create an executable with C++ support
function (add_module_executable TARGET)
    add_executable(${TARGET} ${ARGN})
    target_enable_cxx_modules(${TARGET})
endfunction ()

function (handle_module_reference ESCAPED_TARGET ESCAPED_REFERENCE)
    # message("${ESCAPED_TARGET} refer to ${ESCAPED_REFERENCE}")
    get_target_property(INTERFACE_TARGET ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_TARGET)
    add_dependencies(${ESCAPED_TARGET} ${INTERFACE_TARGET})
endfunction()

## Create C++ module interface.
## add_module_library(TARGET SOURCE <SOURCE> [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
## Set target property below:
##  CXX_MODULE_NAME             Unescaped module name
##  CXX_MODULE_INTERFACE_FILE   Source file path
##  CXX_MODULE_INTERFACE_TARGET Escaped names
##  CXX_MODULE_REFERENCES       Escaped names of referenced modules
function (add_module_library TARGET _SOURCE SOURCE)
    # Set cmake to use CXX compiler on C++ module files
    set_source_files_properties(${SOURCE} PROPERTIES LANGUAGE CXX)

    string(REPLACE ":" ".." ESCAPED_TARGET ${TARGET})

    set(REFERENCES ${ARGN})
    if(REFERENCES)
        list(POP_FRONT REFERENCES _REFERENCE)
        if(NOT ${_REFERENCE} STREQUAL REFERENCE)
            message(WARNING "\"${_REFERENCE}\" should be \"REFERENCE\"")
        endif()
    endif()

    # Create targets for interface files
    set(out_file ${SOURCE}.${CXX_PRECOMPILED_MODULES_EXT})
    set(in_file ${CMAKE_CURRENT_SOURCE_DIR}/${SOURCE})

    # TODO: CXX flags might be different
    set(cmd ${CMAKE_CXX_COMPILER} ${CXX_MODULES_FLAGS} "$<JOIN:$<TARGET_PROPERTY:${ESCAPED_TARGET},COMPILE_OPTIONS>,\ >" ${CXX_MODULES_CREATE_FLAGS} ${in_file} ${CXX_MODULES_OUTPUT_FLAG} ${out_file})
    
    set(ESCAPED_REFERENCES)

    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        get_target_property(NAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        get_target_property(FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        list(APPEND cmd ${CXX_MODULES_USE_FLAG}"${NAME}=${CMAKE_CURRENT_BINARY_DIR}/${FILE}.${CXX_PRECOMPILED_MODULES_EXT}")
        list(APPEND ESCAPED_REFERENCES ${ESCAPED_REFERENCE})
    endforeach ()
    
    get_property(compile_definitions DIRECTORY PROPERTY COMPILE_DEFINITIONS)
    foreach(definition IN LISTS compile_definitions)
        list(APPEND cmd ${CXX_DEFINITION_HEAD}${definition})
    endforeach()

    get_property(options DIRECTORY PROPERTY COMPILE_OPTIONS)
    list(APPEND cmd ${options})

    get_filename_component(out_file_dir ${out_file} DIRECTORY)

    if (out_file_dir)
        file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/${out_file_dir})
    endif()

    # Create interface build target
    add_custom_command(
        OUTPUT ${out_file}
        COMMAND ${cmd}
        DEPENDS ${in_file} ${ESCAPED_REFERENCES}
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    )
    
    # Create interface build target
    add_custom_target(${ESCAPED_TARGET}
        COMMAND ${cmd}
        DEPENDS ${out_file}
        WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    )

    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        handle_module_reference(${ESCAPED_TARGET} ${ESCAPED_REFERENCE})
    endforeach ()

    # Store property with interface file
    set_target_properties(${ESCAPED_TARGET}
        PROPERTIES
        CXX_MODULE_NAME "${TARGET}"
        CXX_MODULE_INTERFACE_FILE "${SOURCE}"
        CXX_MODULE_INTERFACE_TARGET "${ESCAPED_TARGET}"
        CXX_MODULE_REFERENCES "${REFERENCES}"
    )
endfunction ()

## Link a (C++ module) library to (C++ module) target.
## target_link_module_libraries(TARGET SOURCE <SOURCE> [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
function (target_link_module_libraries TARGET _SOURCE SOURCE)
    # Enable modules for target
    add_executable(${TARGET})
    target_sources(${TARGET} PRIVATE ${SOURCE})
    target_enable_cxx_modules(${TARGET})

    set(REFERENCES ${ARGN})
    if(REFERENCES)
        list(POP_FRONT REFERENCES _REFERENCE)
        if(NOT ${_REFERENCE} STREQUAL REFERENCE)
            message(WARNING "\"${_REFERENCE}\" should be \"REFERENCE\"")
        endif()
    endif()

    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        handle_module_reference(${TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${TARGET} 
            PRIVATE "SHELL:${CXX_MODULES_USE_FLAG} ${MODULENAME}=${CMAKE_CURRENT_BINARY_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
    endforeach ()
endfunction ()

function(execute_umake_command command)
    string(REPLACE "\\" "/" command ${command})
    string(REGEX MATCHALL "[0-9/:._a-zA-Z-]+" cmds "${command}")
    list(POP_FRONT cmds head)
    if(${head} STREQUAL "MODULE")
        add_module_library(${cmds})
    elseif(${head} STREQUAL "EXECUTABLE")
        target_link_module_libraries(${cmds})
    else()
        message(FATAL_ERROR "Failed to parse the result of umake. \"${head}\" is not a correct target type.")
    endif()
endfunction()

# umake should be downloaded first
function(add_main_source UMAKE_PATH)
    execute_process(
        COMMAND python ${UMAKE_PATH} --root ${CMAKE_CURRENT_LIST_DIR} --target cmake ${ARGN}
        OUTPUT_VARIABLE RESULT
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    )
    foreach(cmd IN LISTS RESULT)
        execute_umake_command(${cmd})
    endforeach(cmd)
endfunction()