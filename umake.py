"""
A minimal build tool for c++ under MIT license.
Written by TheVeryDarkness, 1853308@tongji.edu.cn on Github.
"""
import os.path as path
from cmake import write_cmake
from config import *
from sys import stderr, stdout
from scan import *


def escapeSource(relSrcToRoot: str):
    return relSrcToRoot.replace("/", "__").replace("\\", "__")


def main():

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
            extHeaders, extSources, extHeaderSourcePairs
        )
        for relFolderToCur in relFoldersToCur:
            scanAllFiles(
                relFolderToCur,
                relRoot,
                excludeFiles,
                excludeDirs,
                encoding,
                ext,
                moduleExtension,
                verbosity,
                logUpdate,
            )
        cleanCache()

        for source in sources:
            relSource = path.relpath(source, relRoot)
            (
                modulesToBePreCompiledBySources[relSource],
                extraSourcesBySources[relSource],
            ) = recursiveCollectDependencies(
                source, relRoot, verbosity, encoding, ext, logUpdate, set()
            )
        for relModuleToRoot in modulesBiDict.values():
            relModuleToCur = path.relpath(path.join(relRoot, relModuleToRoot))
            (
                modulesToBePreCompiledBySources[relModuleToRoot],
                extraSourcesBySources[relModuleToRoot],
            ) = recursiveCollectDependencies(
                relModuleToCur, relRoot, verbosity, encoding, ext, logUpdate, set()
            )
        for relModuleToRoot in implDict.values():
            relModuleToCur = path.relpath(path.join(relRoot, relModuleToRoot))
            (
                modulesToBePreCompiledBySources[relModuleToRoot],
                extraSourcesBySources[relModuleToRoot],
            ) = recursiveCollectDependencies(
                relModuleToCur, relRoot, verbosity, encoding, ext, logUpdate, set()
            )
        if autoObj:
            for extraSourcesBySource in extraSourcesBySources.values():
                extraSourcesToRoot.unionWith(extraSourcesBySource)
            for extraSrcToRoot in extraSourcesToRoot.sources:
                extraSrcToCur = path.relpath(path.join(relRoot, extraSrcToRoot))
                (
                    modulesToBePreCompiledBySources[extraSrcToRoot],
                    extraSourcesBySources[extraSrcToRoot],
                ) = recursiveCollectDependencies(
                    extraSrcToCur, relRoot, verbosity, encoding, ext, logUpdate, set()
                )
                objectsDict[extraSrcToRoot] = escapeSource(extraSrcToRoot)
            updated_one_source = True
            while updated_one_source:
                updated_one_source = False
                for source, extraSourcesToRoot in extraSourcesBySources.copy().items():
                    for extraSrcToRoot in extraSourcesToRoot.sources:
                        extraSrcToCur = path.relpath(path.join(relRoot, extraSrcToRoot))
                        if extraSrcToRoot not in extraSourcesBySources.keys():
                            (
                                modulesToBePreCompiledBySources[extraSrcToRoot],
                                extraSourcesBySources[extraSrcToRoot],
                            ) = recursiveCollectDependencies(
                                extraSrcToCur,
                                relRoot,
                                verbosity,
                                encoding,
                                ext,
                                logUpdate,
                                set(),
                            )
                            objectsDict[extraSrcToRoot] = escapeSource(extraSrcToRoot)
                            updated_one_source = True

        modules_not_found: list[str] = []
        for _source, modulesToBePreCompiled in modulesToBePreCompiledBySources.items():
            for moduleToBePreCompiled in modulesToBePreCompiled.module:
                if moduleToBePreCompiled not in modulesBiDict:
                    print(
                        YELLOW
                        + 'Imported module "{}" from dependencies of {} is not found'.format(
                            moduleToBePreCompiled, _source
                        )
                        + RESET
                    )
                    modules_not_found.append(modulesToBePreCompiled)

        if len(modules_not_found) != 0:
            for _source, _deps in depsDict.items():
                for imported in _deps.modules.module:
                    if imported not in modulesBiDict:
                        print(
                            YELLOW
                            + 'Module "{}" imported from "{}" is not found.'.format(
                                imported, _source
                            )
                            + RESET
                        )

        if target == "info-only":
            print(GREEN + str(modulesToBePreCompiledBySources) + RESET)
            print(BLUE + str(modulesBiDict) + RESET)
            if verbosity >= 2:
                print(str(depsDict))
        elif target == "cmake":
            write_cmake(
                out=stdout,
                modulesToBePreCompiledBySources=modulesToBePreCompiledBySources,
                objectsDict=objectsDict,
                extraSourcesBySources=extraSourcesBySources,
            )
        elif target == "cmake-store":
            with open(relOutToCur, "w", encoding="utf-8") as out:
                write_cmake(
                    out=out,
                    modulesToBePreCompiledBySources=modulesToBePreCompiledBySources,
                    objectsDict=objectsDict,
                    extraSourcesBySources=extraSourcesBySources,
                )
        else:
            print(depsDict)
        if not cacheDisabled:
            saveCache(relRoot)
    except Exception as e:
        print("\t", RED + str(e) + RESET, sep="", file=stderr)
        print(
            RED + "Failed for parsed arguments: {}.".format(args) + RESET, file=stderr
        )
        if not cacheDisabled:
            deleteCache(relRoot)
        if verbosity >= VERBOSITY_SHOW_STACKTRACE:
            print(YELLOW + "Re-raise for stack trace." + RESET)
            raise


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
