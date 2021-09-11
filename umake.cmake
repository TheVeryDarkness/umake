# Under MIT License, see ./License

cmake_minimum_required(VERSION 3.7)

if(NOT ${CMAKE_GENERATOR} STREQUAL "Ninja")
    message(WARNING "Errors may occur with \"${CMAKE_GENERATOR}\", as I may not meet and solve them at the first time. Ninja should work for you.")
endif()

include(CheckCXXCompilerFlag)
set(CXX_DEFINITION_HEAD -D)
set(CXX_PRECOMPILED_MODULES_DIR ${CMAKE_CURRENT_BINARY_DIR}/.cppm)
set(CXX_MODULES_PRECOMPILE_WHEN_COMPILE FALSE)
if(MSVC)
    # See https://docs.microsoft.com/en-us/cpp/preprocessor/predefined-macros
    # See https://docs.microsoft.com/en-us/cpp/error-messages/compiler-warnings/c5050
    set(CXX_MODULES_FOR_CHECK /experimental:module)
    set(CXX_MODULES_FLAGS /nologo /experimental:module)
    set(CXX_PRECOMPILED_MODULES_EXT ifc)
    set(CXX_MODULES_CREATE_FLAGS -c)
    set(CXX_MODULES_SPECIFY_MODULE_NAME TRUE)
    set(CXX_MODULES_PRECOMPILE_WHEN_COMPILE TRUE)

    # It's mentioned in CMakeCxxModules(https://github.com/NTSFka/CMakeCxxModules)
    # I can't find any information in documents.
    if(MSVC_VERSION LESS 1928)
        list(APPEND CXX_MODULES_FLAGS /module:interface)
        set(CXX_MODULES_REFERENCE_FLAG /module:reference)
        set(CXX_MODULES_OUTPUT_FLAG /module:output)
    else()
        list(APPEND CXX_MODULES_FLAGS /interface)
        set(CXX_MODULES_REFERENCE_FLAG /reference)
        set(CXX_MODULES_OUTPUT_FLAG /ifcOutput)
    endif()
    if(NOT ${CXX_MODULES_PRECOMPILE_WHEN_COMPILE})
        if(NOT CMAKE_CXX_STANDARD)
            set(CXX_MODULES_VERSION_FLAG "/std:c++20")
        elseif(${CMAKE_CXX_STANDARD} GREATER 20)
            set(CXX_MODULES_VERSION_FLAG "/std:c++latest")
        else()
            set(CXX_MODULES_VERSION_FLAG "/std:c++20")
        endif()
    endif()
else() # Any more check?
    set(CXX_MODULES_FOR_CHECK -fmodules)
    set(CXX_MODULES_FLAGS -fmodules)
    set(CXX_PRECOMPILED_MODULES_EXT pcm)
    set(CXX_MODULES_CREATE_FLAGS -fmodules -x c++-module --precompile)
    set(CXX_MODULES_REFERENCE_FLAG -fmodule-file=)
    set(CXX_MODULES_OUTPUT_FLAG -o)
    if(NOT ${CXX_MODULES_PRECOMPILE_WHEN_COMPILE})
        if(NOT CMAKE_CXX_STANDARD)
            set(CXX_MODULES_VERSION_FLAG "-std=c++20")
        elseif(${CMAKE_CXX_STANDARD} GREATER 20)
            set(CXX_MODULES_VERSION_FLAG "-std=c++2a")
        else()
            set(CXX_MODULES_VERSION_FLAG "-std=c++20")
        endif()
    endif()
endif()

# Check if c++ compiler supports c++ modules.
# Otherwise raise a fatal error.
check_cxx_compiler_flag(${CXX_MODULES_FOR_CHECK} CXX_MODULES_SUPPORTED)
if (NOT CXX_MODULES_SUPPORTED)
    message(FATAL_ERROR "Compiler \"${CMAKE_CXXCOMPILER_ID}\" doesn't support C++ 20 modules. Checked by flag \"${CXX_MODULES_FOR_CHECK}\"")
endif ()


if(${CMAKE_VERSION} VERSION_LESS 3.15)
    message(WARNING "Clean precompiled modules by yourself at \"${CXX_PRECOMPILED_MODULES_DIR}\".")
endif()

# Add flags to the target to enable module support.
function (target_enable_cxx_modules TARGET)
    target_compile_options(${TARGET} PRIVATE ${CXX_MODULES_FLAGS})
endfunction ()

# Add module dependencies to the target
function(target_add_module_dependencies ESCAPED_TARGET ESCAPED_REFERENCE)
    target_link_libraries(${ESCAPED_TARGET} PUBLIC ${ESCAPED_REFERENCE})

    get_target_property(HAS_IMPLEMENT ${ESCAPED_REFERENCE} CXX_MODULE_HAS_IMPLEMENT)
    if(${HAS_IMPLEMENT})
        message(VERBOSE "${ESCAPED_REFERENCE} has an individual implement unit.")
        if(NOT "__impl__.${ESCAPED_REFERENCE}" STREQUAL ${ESCAPED_TARGET})
            message(DEBUG "Link implement of ${ESCAPED_REFERENCE} to ${ESCAPED_TARGET}.")
            target_link_libraries(${ESCAPED_TARGET} PUBLIC "__impl__.${ESCAPED_REFERENCE}")
        endif()
    endif()

    message(DEBUG "${ESCAPED_TARGET} has a dependency on ${ESCAPED_REFERENCE}")
    add_dependencies(${ESCAPED_TARGET} ${ESCAPED_REFERENCE})
endfunction()

function(add_object_dependency SOURCE REFERENCE)
    if(CXX_MODULES_PRECOMPILE_WHEN_COMPILE)
        get_target_property(INTERFACE_FILE ${REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_source_file_property(INTERFACE_DEPENDS ${SOURCE} OBJECT_DEPENDS)

        set(NEW_OBJECT_DEPEND "${CMAKE_CURRENT_BINARY_DIR}/CMakeFiles/${REFERENCE}.dir/${INTERFACE_FILE}${CMAKE_CXX_OUTPUT_EXTENSION}")

        if(NOT INTERFACE_DEPENDS)
            set(INTERFACE_DEPENDS ${NEW_OBJECT_DEPEND})
        else()
            string(APPEND INTERFACE_DEPENDS ";${NEW_OBJECT_DEPEND}")
        endif()

        message(DEBUG "${SOURCE} has an object dependency on ${NEW_OBJECT_DEPEND}")
        set_property(SOURCE ${SOURCE} PROPERTY OBJECT_DEPENDS ${INTERFACE_DEPENDS})
    endif()
endfunction()

## Create C++ module interface.
## add_module_library(TARGET SOURCE <SOURCE> [REFERENCE <REFERENCE> ...] [DEPEND <DEPEND> ...])
## Set target property below:
##  CXX_MODULE_NAME             Unescaped module name
##  CXX_MODULE_INTERFACE_FILE   Source file path
##  CXX_MODULE_REFERENCES       Escaped names of referenced modules
function (add_module_library TARGET _SOURCE SOURCE)
    if(NOT ${_SOURCE} STREQUAL SOURCE)
        message(FATAL_ERROR "\"${_SOURCE}\" should be \"SOURCE\"")
    endif()
    # Set cmake to use CXX compiler on C++ module files
    set_source_files_properties(${SOURCE} PROPERTIES LANGUAGE CXX)

    string(REPLACE ":" ".." ESCAPED_TARGET ${TARGET})

    set(HAS_IMPLEMENT FALSE)
    set(DEPENDS)
    set(REFERENCES)
    set(MODE)
    foreach(TOKEN IN LISTS ARGN)
        if(${TOKEN} STREQUAL DEPEND)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL REFERENCE)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL IMPLEMENT)
            set(HAS_IMPLEMENT TRUE)
        else()
            if(NOT MODE)
                message(FATAL_ERROR "Mode not set.")
            endif()
            list(APPEND ${MODE}S ${TOKEN})
        endif()
    endforeach()

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
    # Select object libraries would cause errors if you use Visual Studio generators
    if("${CMAKE_GENERATOR}" STREQUAL Ninja)
        add_library(${ESCAPED_TARGET} OBJECT ${SOURCE} ${IMPLEMENTS})
    else()
        add_library(${ESCAPED_TARGET} STATIC ${SOURCE} ${IMPLEMENTS})
    endif()
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
    endforeach()

    if(${CXX_MODULES_PRECOMPILE_WHEN_COMPILE})
        target_compile_options(${ESCAPED_TARGET} PRIVATE "${CXX_MODULES_OUTPUT_FLAG}${OUT_FILE}")
    else()
        # TODO: CXX flags might be different
        set(cmd ${CMAKE_CXX_COMPILER} ${CXX_MODULES_FLAGS} ${CXX_MODULES_VERSION_FLAG} "$<JOIN:$<TARGET_PROPERTY:${ESCAPED_TARGET},COMPILE_OPTIONS>,\ >" ${CXX_MODULES_CREATE_FLAGS} ${IN_FILE} ${CXX_MODULES_OUTPUT_FLAG} ${OUT_FILE})
        set(ESCAPED_REFERENCES)
        foreach (REFERENCE IN LISTS REFERENCES)
            string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
            get_target_property(FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
            get_target_property(NAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
            list(APPEND cmd ${CXX_MODULES_REFERENCE_FLAG} "${NAME}=${CXX_PRECOMPILED_MODULES_DIR}/${FILE}.${CXX_PRECOMPILED_MODULES_EXT}")
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
        message("${CMAKE_CONFIGURATION_TYPES}")
        if(CMAKE_BUILD_TYPE)
            string(TOUPPER ${CMAKE_BUILD_TYPE} UPPER_BUILD_TYPE)
            if(CMAKE_CXX_FLAGS_${UPPER_BUILD_TYPE})
                separate_arguments(FLAGS NATIVE_COMMAND ${CMAKE_CXX_FLAGS_${UPPER_BUILD_TYPE}})
                foreach(flag IN LISTS FLAGS)
                    list(APPEND cmd ${flag})
                endforeach()
            endif()
        endif()

        add_custom_command(
            OUTPUT ${OUT_FILE}
            COMMAND ${cmd}
            DEPENDS ${IN_FILE} ${ESCAPED_REFERENCES}
            WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
        )
        set(PRECOMPILING_TARGET ".PRECOMPILED.${ESCAPED_TARGET}")
        # Create interface build target
        add_custom_target(${PRECOMPILING_TARGET}
            COMMAND ${cmd}
            DEPENDS ${OUT_FILE} ${ESCAPED_REFERENCES}
            WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
        )
        foreach(ESCAPED_REFERENCE IN LISTS ESCAPED_REFERENCES)
            target_add_module_dependencies(${PRECOMPILING_TARGET} ${ESCAPED_REFERENCE})
        endforeach()

        message(DEBUG "${ESCAPED_TARGET} has a dependency on ${PRECOMPILING_TARGET}")
        add_dependencies(${ESCAPED_TARGET} ${PRECOMPILING_TARGET})
    endif()

    # Store property with interface file
    set_target_properties(${ESCAPED_TARGET}
        PROPERTIES
        CXX_MODULE_NAME "${TARGET}"
        CXX_MODULE_INTERFACE_FILE "${SOURCE}"
        CXX_MODULE_REFERENCES "${REFERENCES}"
        CXX_MODULE_HAS_IMPLEMENT "${HAS_IMPLEMENT}"
    )

    set(OBJECT_PATH "${CMAKE_CURRENT_BINARY_DIR}/CMakeFiles/${REFERENCE}.dir/${INTERFACE_FILE}${CMAKE_CXX_OUTPUT_EXTENSION}")
    if(${CMAKE_VERSION} VERSION_GREATER_EQUAL 3.15)
        get_property(_CLEAN_FILES TARGET ${ESCAPED_TARGET} PROPERTY ADDITIONAL_CLEAN_FILES)
        if(NOT ${_CLEAN_FILES})
            set(_CLEAN_FILES ${OUT_FILE})
        else()
            string(APPEND _CLEAN_FILES ${OUT_FILE})
        endif()
        set_property(TARGET ${ESCAPED_TARGET} PROPERTY ADDITIONAL_CLEAN_FILES ${_CLEAN_FILES})
        set_property(
            TARGET ${ESCAPED_TARGET}
            PROPERTY ADDITIONAL_CLEAN_FILES
            OBJECT_PATH
        )
    else()
        if(EXISTS ${OBJECT_PATH})
            message(STATUS "Cleaning ${OBJECT_PATH}.")
            file(REMOVE ${OBJECT_PATH})
        endif()
    endif()
endfunction ()

function(add_module_implement TARGET _SOURCE SOURCE)
    if(NOT ${_SOURCE} STREQUAL SOURCE)
        message(FATAL_ERROR "\"${_SOURCE}\" should be \"SOURCE\"")
    endif()
    
    # Set cmake to use CXX compiler on C++ module files
    set_source_files_properties(${SOURCE} PROPERTIES LANGUAGE CXX)

    string(REPLACE ":" ".." ESCAPED_TARGET ${TARGET})
    string(CONCAT IMPLEMENT_TARGET "__impl__." ${ESCAPED_TARGET})

    set(DEPENDS)
    set(REFERENCES)
    set(MODE)
    foreach(TOKEN IN LISTS ARGN)
        if(${TOKEN} STREQUAL DEPEND)
            set(MODE ${TOKEN})
        elseif(${TOKEN} STREQUAL REFERENCE)
            set(MODE ${TOKEN})
        else()
            if(NOT MODE)
                message(FATAL_ERROR "Mode not set.")
            endif()
            list(APPEND ${MODE}S ${TOKEN})
        endif()
    endforeach()

    add_library(${IMPLEMENT_TARGET} STATIC ${SOURCE})

    add_dependencies(${IMPLEMENT_TARGET} ${ESCAPED_TARGET})
    add_dependencies(${IMPLEMENT_TARGET} ${DEPENDS})
    message(DEBUG "Link ${DEPENDS} to ${IMPLEMENT_TARGET}.")
    target_link_libraries(${IMPLEMENT_TARGET} PUBLIC ${DEPENDS})
    
    list(APPEND REFERENCES ${ESCAPED_TARGET})
    # Select object libraries would cause errors if you use Visual Studio generators
    foreach (REFERENCE IN LISTS REFERENCES)
        string(REPLACE ":" ".." ESCAPED_REFERENCE ${REFERENCE})
        target_add_module_dependencies(${IMPLEMENT_TARGET} ${ESCAPED_REFERENCE})
        get_target_property(INTERFACE_FILE ${ESCAPED_REFERENCE} CXX_MODULE_INTERFACE_FILE)
        get_target_property(MODULENAME ${ESCAPED_REFERENCE} CXX_MODULE_NAME)
        # Avoid de-duplication
        target_compile_options(${IMPLEMENT_TARGET}
            PRIVATE "SHELL:${CXX_MODULES_REFERENCE_FLAG} ${MODULENAME}=${CXX_PRECOMPILED_MODULES_DIR}/${INTERFACE_FILE}.${CXX_PRECOMPILED_MODULES_EXT}"
        )
        add_object_dependency(${SOURCE} ${ESCAPED_REFERENCE})
    endforeach()
endfunction()

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

    message(DEBUG "${TARGET} has a dependency on ${DEPENDS}")
    add_dependencies(${TARGET} ${DEPENDS})
    target_link_libraries(${TARGET} PUBLIC ${DEPENDS})

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

    message(DEBUG "${TARGET} has a dependency on ${DEPENDS}")
    add_dependencies(${TARGET} ${DEPENDS})
    target_link_libraries(${TARGET} PUBLIC ${DEPENDS})

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

    target_link_libraries(${TARGET} PUBLIC ${DEPENDS})

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
    elseif("IMPLEMENT" STREQUAL ${head})
        add_module_implement(${cmds})
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
    elseif("IMPLEMENT" STREQUAL ${head})
        add_module_implement(${cmds})
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
        if(${CMAKE_VERSION} VERSION_LESS 3.19)
            message(WARNING "CMake doesn't support parsing json string yet. Pass \"umake.py\" path instead.")
        endif()

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
        ERROR_VARIABLE ERROR
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    )
    message(VERBOSE ${RESULT})
    if(ERROR)
        if(RESULT)
            message("STDOUT:")
            message(${RESULT})
        endif()
        message("STDERR")
        message(${ERROR})
        message(FATAL_ERROR "Error detected during scanning dependencies.")
    endif()
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