"""
A minimal build tool for c++ under MIT license.
Written by TheVeryDarkness, 1853308@tongji.edu.cn on Github.
"""
import argparse
import json
import os.path as path
import os
from posixpath import relpath
from sys import stderr

from scan import *
from generate import *


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', type=str,
                        help="The main target and its source file to compile and link to.")
    parser.add_argument("-p", "--project", type=str,
                        help="The path to thr source file folder for the project. Every file in this folder may be scanned for module, especially if the project uses import. Root by default.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Verbosity level.")
    parser.add_argument("-r", "--root", type=str,
                        help="The root path to generate build file, such as makefile or scripts.")
    parser.add_argument("-t", "--target", type=str,
                        help="The target format of build file.")
    parser.add_argument("-M", "--module", type=str, nargs="+", default=[
                        ".ixx", ".mpp", ".cppm"], help="Possible extension names of cpp module interface files.")
    parser.add_argument("-e", "--encoding", type=str,
                        default="UTF-8", help="The encoding of source files.")
    parser.add_argument("-E", "--exclude", nargs="+",
                        type=str, help="Folders to be excluded.")
    parser.add_argument("-c", "--cc", type=str, help="C compiler")
    parser.add_argument("-C", "--cxx", type=str, help="C++ compiler")
    args = parser.parse_args()

    root: str = args.root
    assert path.isdir(root)
    relRoot = path.relpath(root)

    assert len(args.sources) % 2 == 0, "Target should match source"
    target_source_pairs: list[tuple[str, str]] = [(args.sources[2*i], path.relpath(args.sources[2*i+1], relRoot))
                                                  for i in range(len(args.sources)//2)]
    targetsBidict: bidict[str, str] = bidict(target_source_pairs)
    # target <--> source
    sources: list[str] = [
        path.relpath(args.sources[2*i+1]) for i in range(len(args.sources)//2)
    ]
    verbosity: int = args.verbose
    target: str = args.target
    encoding: str = args.encoding
    project: str = args.project
    moduleExtension: list[str] = args.module
    if not project and root:
        project = root
    else:
        if verbosity >= 1:
            print("No project source file directory given, so your modules, if imported somewhere, may not be found, unless you specify all of them in args.")

    modulesToBePreCompiledByEachSource: dict[str, modulesDependency] = dict()

    load(relRoot)

    try:
        for source in sources:
            relSource = path.relpath(source, relRoot)
            modulesToBePreCompiledByEachSource[relSource] = recursiveScanLocalDependencies(
                source, relRoot, verbosity, encoding)
        for dir, dirs, files in os.walk(project):
            for file in files:
                nothing, ext = path.splitext(file)
                relFileToCur = path.relpath(path.join(dir, file))
                relFileToRoot = path.relpath(relFileToCur, relRoot)
                if ext not in moduleExtension:
                    if verbosity >= 4:
                        print(
                            "Walked-through file \"{}\" has a different extension name, skipped.".format(relFileToCur))
                    continue
                modulesToBePreCompiledByEachSource[relFileToRoot] = recursiveScanLocalDependencies(
                    relFileToCur, relRoot, verbosity, encoding)
        modules_not_found: list[str] = []
        for _source, modulesToBePreCompiled in modulesToBePreCompiledByEachSource.items():
            for moduleToBePreCompiled in modulesToBePreCompiled.module:
                if moduleToBePreCompiled not in modulesBiDict:
                    print(
                        YELLOW+"Imported module \"{}\" from dependencies of {} is not found".format(moduleToBePreCompiled, _source)+RESET)
                    modules_not_found.append(modulesToBePreCompiled)

        if len(modules_not_found) != 0:
            for _source, _deps in depsDict.items():
                for imported in _deps.modules.module:
                    if imported not in modulesBiDict:
                        print(
                            YELLOW+"Module \"{}\" imported from \"{}\" is not found.".format(imported, _source)+RESET)

        for module in modulesBiDict.keys():
            if '_' in module:
                if verbosity >= 1:
                    print(YELLOW + "Avoid _ in module name" + RESET)

        if target == "info-only":
            print(GREEN + str(modulesToBePreCompiledByEachSource) + RESET)
            print(BLUE + str(modulesBiDict) + RESET)
            if verbosity >= 2:
                print(str(depsDict))
        elif target == "cmake":
            built: list[str] = []
            while len(built) < len(modulesToBePreCompiledByEachSource):
                has_built_one_in_one_loop = False
                for source, modules in modulesToBePreCompiledByEachSource.items():
                    reference = False
                    if source in built or any([modulesBiDict[module] not in built for module in modules.module]):
                        continue
                    has_built_one_in_one_loop = True
                    if len(built) != 0:
                        print(';')
                    if source in modulesBiDict.inverse:
                        print(
                            'MODULE', modulesBiDict.inverse[source], 'SOURCE', end=' ')
                    else:
                        print('EXECUTABLE',
                              targetsBidict.inverse[source], "SOURCE", end=' ')
                    print(source, end=' ')
                    for module in built:  # Should be modules.module:
                        if module in modulesBiDict.inverse:
                            if not reference:
                                print('REFERENCE', end=' ')
                                reference = True
                            print(modulesBiDict.inverse[module], end=' ')
                    built.append(source)

                assert has_built_one_in_one_loop, "Cyclic imports"
        elif target == 'ninja':
            print(RED + "Ninja support is not tested." + RESET)
            generate_ninja(path.join(relRoot, "build.ninja"),
                           modulesToBePreCompiledByEachSource)
        else:
            raise Exception("Unknown target")
    except Exception as e:
        print('\t', RED + str(e) + RESET, sep="", file=stderr)
        print(RED + "Failed for parsed arguments: {}.".format(args) +
              RESET, file=stderr)
    save(relRoot)


if __name__ == "__main__":
    # import profile
    # profile.run("main()")
    # import cProfile
    # cProfile.run("main()")
    main()

    # import tracemalloc
    # tracemalloc.start()

    # main()

    # snapshot = tracemalloc.take_snapshot()
    # top_stats = snapshot.statistics('lineno')

    # print("[ Top 10 ]")
    # for stat in top_stats[:10]:
    #     print(stat)
