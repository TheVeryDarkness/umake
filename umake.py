"""
A minimal build tool for c++ under MIT license.
Written by TheVeryDarkness, 1853308@tongji.edu.cn on Github.
"""
import argparse
import os.path as path
import os
from sys import stderr, argv

from scan import *
from generate import *

CONFIG_PATH = "umakeConfig.json"


def escapeSource(relSrcToRoot: str):
    return relSrcToRoot.replace('/', '__').replace('\\', '__')


def loadConfig(args: argparse.Namespace, preferred: bool):
    configPath = path.join(args.root, CONFIG_PATH)
    if not path.exists(configPath) and not preferred:
        return
    with open(configPath) as config:
        cfg = json.load(config)
        for key, value in cfg.items():
            if preferred or key not in vars(args).keys():
                vars(args)[key] = value


def saveConfig(args: argparse.Namespace):
    vars(args)["umake.py"] = argv[0]
    with open(path.join(args.root, CONFIG_PATH), 'w') as config:
        json.dump(vars(args), config)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='*', type=str,
                        help="The main target and its source file to compile and link to.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Verbosity level. Repeat this option to increase.")
    parser.add_argument("-r", "--root", type=str, default='.',
                        help="The root path to generate build file, such as makefile or scripts. Current working directory by default.")
    parser.add_argument("-p", "--project", type=str,
                        help="The path to the source file folder for the project. Every file in this folder may be scanned for module exports. Root by default.")
    parser.add_argument("-t", "--target", type=str,
                        help="The target format of output.")
    parser.add_argument("-M", "--module", type=str, nargs="+",
                        default=[".ixx", ".mpp", ".cppm"],
                        help="Possible extension names of cpp module interface files. Other files will be skipped during modules scanning.")
    parser.add_argument("-e", "--encoding", type=str,
                        default="UTF-8", help="The encoding of source files.")
    parser.add_argument("-Ed", "--exclude-dirs", action="append", default=[],
                        type=str, help="Folders to be excluded. Treated as regex.")
    parser.add_argument("-Ef", "--exclude-files", action="append", default=[],
                        type=str, help="Files to be excluded. Treated as regex.")
    parser.add_argument("--no-auto-obj", action="store_true",
                        help="Turn off object dependency output.")
    parser.add_argument("-c", "--cc", type=str, help="C compiler.")
    parser.add_argument("-C", "--cxx", type=str, help="C++ compiler.")
    parser.add_argument("-eh", "--ext-header", nargs="*", default=[],
                        help="Extension names of headers.")
    parser.add_argument("-es", "--ext-source", nargs="*", default=[],
                        help="Extension names of sources.")
    parser.add_argument("-ehs", "--ext-header-source", nargs=2, default=[[".hh", ".cc"], [".hpp", ".cpp"], [".h", ".c"]],
                        help="Extension name pairs of header and sources. Only corresponding sources of scanned headers will be added to object dependencies.")
    parser.add_argument("--save-config", action="store_true",
                        help="Ask umake to generate umakeConfig.json and save configurations.")
    parser.add_argument_group()
    parser.add_argument("--load-config", action="store_true",
                        help="Ask umake to read and load umakeConfig.json on root. Configuration will be preferred unless not given.")
    parser.add_argument("--prefer-config", action="store_true",
                        help="Configuration will be preferred unless not given.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable scanning caches")
    args = parser.parse_args()

    _loadConfig = args.load_config
    _saveConfig = args.save_config
    _preferConfig = args.prefer_config

    if _loadConfig:
        loadConfig(args, _preferConfig)
    if _saveConfig:
        saveConfig(args)

    if not args.project:
        args.project = args.root

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
    relSourcesToRoot = [path.relpath(relSourceToCur, relRoot)
                        for relSourceToCur in sources]
    verbosity: int = args.verbose
    target: str = args.target
    encoding: str = args.encoding
    project: str = args.project
    moduleExtension: list[str] = args.module
    excludeFiles = args.exclude_files
    excludeDirs = args.exclude_dirs
    cacheDisabled = args.no_cache

    autoObj = not args.no_auto_obj
    extHeaders: set[str] = set(args.ext_header)
    extSources: set[str] = set(args.ext_source)
    extHeaderSourcePairs: dict[str, str] = dict(args.ext_header_source)

    modulesToBePreCompiledBySources: dict[str, modulesDependency] = dict()

    # relSrcToRoot <--> relExtraSrcToRoot
    extraSourcesBySources: dict[str, sourcesDependency] = dict()
    extraSourcesToRoot: sourcesDependency = sourcesDependency(set())
    # relSrcToRoot <--> targetName
    objectsDict: bidict[str, str] = bidict()

    if not cacheDisabled:
        loadCache(relRoot)

    try:
        ext: extensionMapper = extensionMapper(
            extHeaders, extSources, extHeaderSourcePairs)
        for source in sources:
            relSource = path.relpath(source, relRoot)
            modulesToBePreCompiledBySources[relSource], extraSourcesBySources[relSource] = recursiveScanLocalDependencies(
                source, relRoot, verbosity, encoding, ext)
        for dir, dirs, files in os.walk(project):
            relDirToCur = path.relpath(dir)
            relDirToRoot = path.relpath(relDirToCur, relRoot)
            for excludeDir in excludeDirs:
                if path.exists(relDirToRoot) and path.exists(excludeDir) and path.samefile(relDirToRoot, excludeDir):
                    if verbosity >= 4:
                        print(
                            "Walked-through dir \"{}\" is excluded as it matches \"{}\"."
                            .format(relDirToCur, excludeDir)
                        )
                    continue
            for file in files:
                nothing, extName = path.splitext(file)
                relFileToCur = path.relpath(path.join(dir, file))
                relFileToRoot = path.relpath(relFileToCur, relRoot)
                for excludeFile in excludeFiles:
                    if path.samefile(relFileToRoot, excludeFile):
                        if verbosity >= 4:
                            print(
                                "Walked-through file \"{}\" is excluded as it matches \"{}\"."
                                .format(relFileToCur, excludeFile)
                            )
                        continue
                if extName not in moduleExtension:
                    if verbosity >= 4:
                        print(
                            "Walked-through file \"{}\" has a different extension name, skipped."
                            .format(relFileToCur)
                        )
                    continue
                modulesToBePreCompiledBySources[relFileToRoot], extraSourcesBySources[relFileToRoot] = recursiveScanLocalDependencies(
                    relFileToCur, relRoot, verbosity, encoding, ext)
        if autoObj:
            for extraSourcesBySource in extraSourcesBySources.values():
                extraSourcesToRoot.unionWith(extraSourcesBySource)
            for extraSrcToRoot in extraSourcesToRoot.sources:
                extraSrcToCur = path.relpath(
                    path.join(relRoot, extraSrcToRoot))
                modulesToBePreCompiledBySources[extraSrcToRoot], extraSourcesBySources[extraSrcToRoot] = recursiveScanLocalDependencies(
                    extraSrcToCur, relRoot, verbosity, encoding, ext)
                objectsDict[extraSrcToRoot] = escapeSource(extraSrcToRoot)
            updated_one_source = True
            while updated_one_source:
                updated_one_source = False
                for source, extraSourcesToRoot in extraSourcesBySources.copy().items():
                    for extraSrcToRoot in extraSourcesToRoot.sources:
                        if extraSrcToRoot not in extraSourcesBySources.keys():
                            modulesToBePreCompiledBySources[extraSrcToRoot], extraSourcesBySources[extraSrcToRoot] = recursiveScanLocalDependencies(
                                relFileToCur, relRoot, verbosity, encoding, ext)
                            objectsDict[extraSrcToRoot] = escapeSource(
                                extraSrcToRoot)
                            updated_one_source = True

        modules_not_found: list[str] = []
        for _source, modulesToBePreCompiled in modulesToBePreCompiledBySources.items():
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
            print(GREEN + str(modulesToBePreCompiledBySources) + RESET)
            print(BLUE + str(modulesBiDict) + RESET)
            if verbosity >= 2:
                print(str(depsDict))
        elif target == "cmake":
            built: list[str] = []
            while len(built) < len(modulesToBePreCompiledBySources):
                has_built_one_in_one_loop = False
                for source, modules in modulesToBePreCompiledBySources.items():
                    depend = False
                    reference = False
                    if (
                        source in built
                        or
                        any(
                            [modulesBiDict[module]
                                not in built for module in modules.module]
                        )
                    ):
                        continue
                    has_built_one_in_one_loop = True
                    if source in modulesBiDict.inverse:
                        print('MODULE', modulesBiDict.inverse[source], 'SOURCE',
                              end=' ')
                    elif source in relSourcesToRoot:
                        print('EXECUTABLE', targetsBidict.inverse[source], "SOURCE",
                              end=' ')
                    else:
                        if not autoObj:
                            continue
                        print('OBJECT', objectsDict[source], 'SOURCE', end=' ')
                    print(source, end=' ')

                    for extraSourcesBySource in extraSourcesBySources[source].sources:
                        if extraSourcesBySource == source:
                            continue
                        if not depend:
                            print('DEPEND', end=' ')
                            depend = True
                        print(objectsDict[extraSourcesBySource], end=' ')
                    for module in built:  # Should be modules.module:
                        if module in modulesBiDict.inverse:
                            if not reference:
                                print('REFERENCE', end=' ')
                                reference = True
                            print(modulesBiDict.inverse[module], end=' ')
                    built.append(source)
                    if len(built) < len(modulesToBePreCompiledBySources):
                        print(';')

                assert has_built_one_in_one_loop, "Cyclic imports"
        elif target == 'ninja':
            print(RED + "Ninja support is not tested." + RESET)
            generate_ninja(path.join(relRoot, "build.ninja"),
                           modulesToBePreCompiledBySources)
        else:
            raise Exception("Unknown target")
    except Exception as e:
        print('\t', RED + str(e) + RESET, sep="", file=stderr)
        print(RED + "Failed for parsed arguments: {}.".format(args) +
              RESET, file=stderr)
    if not cacheDisabled:
        saveCache(relRoot)


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
