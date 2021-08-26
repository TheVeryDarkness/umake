"""
A minimal build tool for c++ under MIT license.
Written by TheVeryDarkness, 1853308@tongji.edu.cn on Github.
"""
import argparse
from bidict import bidict
from colorama import Fore, init
import os.path as path
import os

from scan import *
from generate import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", metavar="source", nargs="+",
                        type=str, help="The main source file to compile and link to.")
    parser.add_argument("-p", "--project", type=str,
                        help="The path to thr source file folder for the project. Every file in this folder may be scanned for module, especially if the project uses import. Root by default.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="More verbose output.")
    parser.add_argument("-r", "--root", type=str,
                        help="The root path to generate build file, such as makefile or scripts.")
    parser.add_argument("-t", "--target", type=str,
                        default="dict", help="The target format of build file.")
    parser.add_argument("-M", "--module", type=str, nargs="+", default=[
                        ".ixx", ".mpp", ".cppm"], help="Possible extension names of cpp module interface files.")
    parser.add_argument("-e", "--encoding", type=str,
                        default="UTF-8", help="The encoding of source files.")
    parser.add_argument("-E", "--exclude", nargs="+",
                        type=str, help="Folders to be excluded.")
    parser.add_argument("-c", "--cc", type=str, help="C compiler")
    parser.add_argument("-C", "--cxx", type=str, help="C++ compiler")
    args = parser.parse_args()

    sources: list[str] = args.sources
    verbosity: int = args.verbose
    root: str = args.root
    target: str = args.target
    encoding: str = args.encoding
    project: str = args.project
    module: list[str] = args.module
    if not project and root:
        project = root
    else:
        if verbosity >= 1:
            print("No project source file directory given, so your modules, if imported somewhere, may not be found, unless you specify all of them in args.")

    assert path.isdir(root)
    relRoot = path.relpath(root)
    depsDict: dict[str, tuple[list[str], list[str],
                              list[str], list[str], list[str], list[str]]] = dict()
    modulesToBePreCompiledByEachSource = dict()
    try:
        for source in sources:
            modulesToBePreCompiledByEachSource[source] = recursiveScanLocalDependencies(
                source, relRoot, depsDict, verbosity, encoding)
        for dir, dirs, files in os.walk(project):
            for file in files:
                nothing, ext = path.splitext(file)
                relFileToCur = path.relpath(path.join(dir, file))
                relFileToRoot = path.relpath(relFileToCur, relRoot)
                if ext not in module:
                    if verbosity >= 4:
                        print(
                            "Walked-through file \"{}\" has a different extension name, skipped.".format(relFileToCur))
                    continue
                if relFileToRoot not in depsDict:
                    modulesToBePreCompiledByEachSource[relFileToRoot] = recursiveScanLocalDependencies(
                        relFileToCur, relRoot, depsDict, verbosity, encoding)
        modules_not_found: list[str] = []
        for _source, modulesToBePreCompiled in modulesToBePreCompiledByEachSource.items():
            for moduleToBePreCompiled in modulesToBePreCompiled[2]:
                if moduleToBePreCompiled not in modulesBiDict:
                    print(
                        YELLOW+"Imported module \"{}\" from dependencies of {} is not found".format(moduleToBePreCompiled, _source)+RESET)
                    modules_not_found.append(modulesToBePreCompiled)
        if len(modules_not_found) != 0:
            for _source, _deps in depsDict.items():
                for imported in _deps[2]:
                    if imported not in modulesBiDict:
                        print(
                            YELLOW+"Module \"{}\" imported from \"{}\" is not found.".format(imported, _source)+RESET)
        if target == "dict":
            print(GREEN + str(modulesToBePreCompiledByEachSource) + RESET)
            print(BLUE + str(modulesBiDict) + RESET)
            if verbosity >= 2:
                print(str(depsDict))
        else:
            raise Exception("Unknown target")
    except Exception as e:
        print('\t', RED + str(e) + RESET, sep="")
        print(RED + "Failed for parsed arguments: {}.".format(args) + RESET)


if __name__ == "__main__":
    # import profile
    # profile.run("main()")
    main()
