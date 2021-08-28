# Under MIT License, see ./License
cmake_minimum_required(VERSION 3.0)

include(CheckCXXCompilerFlag)
set(CXX_DEFINITION_HEAD -D)
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
        set(CXX_MODULES_USE_FLAG /module:reference)
        set(CXX_MODULES_OUTPUT_FLAG /module:output)
    else()
        list(APPEND CXX_MODULES_FLAGS /interface)
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
function(add_module_executable TARGET)
    add_executable(${TARGET} ${ARGN})
    target_enable_cxx_modules(${TARGET})
endfunction ()

function(handle_module_reference ESCAPED_TARGET ESCAPED_REFERENCE)
    # message("${ESCAPED_TARGET} refer to ${ESCAPED_REFERENCE}")
    get_target_property(INTERFACE_TARGET ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_TARGET)
    add_dependencies(${ESCAPED_TARGET} ${INTERFACE_TARGET})
endfunction()

## Create C++ module interface.
## add_module(TARGET SOURCE <SOURCE> [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
## Set target property below:
##  CXX_MODULE_NAME             Unescaped module name
##  CXX_MODULE_INTERFACE_FILE   Source file path
##  CXX_MODULE_INTERFACE_TARGET Escaped names
##  CXX_MODULE_REFERENCES       Escaped names of referenced modules
function (add_module TARGET _SOURCE SOURCE)
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
    
    # Add definitions and flags to the target
    get_property(compile_definitions DIRECTORY PROPERTY COMPILE_DEFINITIONS)
    foreach(definition IN LISTS compile_definitions)
        list(APPEND cmd ${CXX_DEFINITION_HEAD}${definition})
    endforeach()
    get_property(compile_definitions GLOBAL PROPERTY COMPILE_DEFINITIONS)
    foreach(definition IN LISTS compile_definitions)
        list(APPEND cmd ${CXX_DEFINITION_HEAD}${definition})
    endforeach()

    separate_arguments(FLAGS NATIVE_COMMAND ${CMAKE_CXX_FLAGS})
    foreach(flag IN LISTS FLAGS)
        list(APPEND cmd ${flag})
    endforeach()

    string(TOUPPER ${CMAKE_BUILD_TYPE} UPPER_BUILD_TYPE)

    if(CMAKE_CXX_FLAGS_${CMAKE_BUILD_TYPE})
        separate_arguments(FLAGS NATIVE_COMMAND ${CMAKE_CXX_FLAGS_${CMAKE_BUILD_TYPE}})
        foreach(flag IN LISTS FLAGS)
            list(APPEND cmd ${flag})
        endforeach()
    endif()
    if(CMAKE_CXX_FLAGS_${UPPER_BUILD_TYPE})
        separate_arguments(FLAGS NATIVE_COMMAND ${CMAKE_CXX_FLAGS_${UPPER_BUILD_TYPE}})
        foreach(flag IN LISTS FLAGS)
            list(APPEND cmd ${flag})
        endforeach()
    endif()

    # Make directory for pre-compiled modules
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
## add_moduled_executable(TARGET SOURCE <SOURCE> [DEPENDS <DEPEND1> [<DEPEND2> ...]] [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
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
        handle_module_reference(${TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${TARGET} 
            PRIVATE "SHELL:${CXX_MODULES_USE_FLAG} ${MODULENAME}=${CMAKE_CURRENT_BINARY_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
    endforeach ()
endfunction ()

## Create static libraries that correspond to single source file.
##  add_object(TARGET SOURCE <SOURCE> [DEPENDS <DEPEND1> [<DEPEND2> ...]] [REFERENCE <REFERENCE1> [<REFERENCE2> ...]])
function(add_object TARGET)
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
        handle_module_reference(${TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${TARGET} 
            PRIVATE "SHELL:${CXX_MODULES_USE_FLAG} ${MODULENAME}=${CMAKE_CURRENT_BINARY_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
    endforeach ()
endfunction()

function(execute_umake_command command)
    string(REPLACE "\\" "/" command ${command})
    string(REGEX MATCHALL "[0-9/:._a-zA-Z-]+" cmds "${command}")
    list(POP_FRONT cmds head)
    if("MODULE" STREQUAL ${head})
        add_module(${cmds})
    elseif("EXECUTABLE" STREQUAL ${head})
        add_moduled_executable(${cmds})
    elseif("OBJECT" STREQUAL ${head})
        add_object(${cmds})
    else()
        message(FATAL_ERROR "Failed to parse the result of umake. \"${head}\" is not a correct target type.")
    endif()
endfunction()

# umake should be downloaded first
function(add_main_source)
    math(EXPR ODD "${ARGC}%2")
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
    foreach(cmd IN LISTS RESULT)
        execute_umake_command(${cmd})
    endforeach(cmd)
endfunction()