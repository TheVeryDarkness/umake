"""
A minimal dependencies scanning tool for c++ under MIT license.
Written by TheVeryDarkness, 1853308@tongji.edu.cn on Github.
"""
from __future__ import annotations
from sys import stderr

from typing import Any, Optional, Union
from bidict import bidict
from colorama import Fore, init
import json
import os
import os.path as path
import re
import time

init()
GREEN: str = Fore.GREEN
BLUE: str = Fore.BLUE
CYAN: str = Fore.CYAN
YELLOW: str = Fore.YELLOW
RED: str = Fore.RED
RESET: str = Fore.RESET
linesep = '\n'

VERBOSITY_SHOW_STACKTRACE = 1
VERBOSITY_SCANNING_FILE = 1
VERBOSITY_MODIFIED_FILE = 2
VERBOSITY_UNMODIFIED_FILE = 3
VERBOSITY_EXCLUDE_DIRECTORY = 4
VERBOSITY_EXCLUDE_FILE = 4
VERBOSITY_INCLUDING_HEADER = 4
VERBOSITY_EXPORTING = 5
VERBOSITY_DROPPING_FILE_CONTENT = 6

def __removeSpace(s: str):
    return s.strip().replace(' ', '').replace('\t', '')


def __uniqueMin(*numbers: int):
    res = min(filter(lambda n: n != -1, numbers))
    assert numbers.count(res) == 1
    return res


class headersDependency:
    def __init__(self, library: set[str], local: set[str]) -> None:
        self.local = local
        self.library = library

    def __len__(self) -> int:
        return sum([0 if len(self.__dict__[key]) == 0 else 1 for key in ["local", "library"]])

    def __repr__(self) -> str:
        return str(vars(self))


class modulesDependency:
    def __init__(self, module: set[str], library: set[str], local: set[str]) -> None:
        self.module = module
        self.library = library
        self.local = local

    def __len__(self) -> int:
        return sum([0 if len(self.__dict__[key]) == 0 else 1 for key in ["module", "library", "local"]])

    def unionWith(self, newDeps: modulesDependency):
        self.module = self.module.union(newDeps.module)
        self.library = self.library.union(newDeps.library)
        self.local = self.library.union(newDeps.local)

    def contain(self, module: set[str], library: set[str], local: set[str]) -> bool:
        return self.module.issuperset(module) and self.library.issuperset(library) and self.local.issuperset(local)

    def __repr__(self) -> str:
        return str(vars(self))


class sourcesDependency:
    def __init__(self, sources: set[str]) -> None:
        '''
        To root
        '''
        self.sources = sources

    def unionWith(self, newDeps: sourcesDependency):
        self.sources = self.sources.union(newDeps.sources)

    def contain(self, sources: set[str]) -> bool:
        return self.sources.issuperset(sources)


    def __repr__(self) -> str:
        return str(vars(self))


class dependency:
    def __init__(self, time: float, headers: Optional[headersDependency] = None, modules: Optional[modulesDependency] = None, provide: Optional[str] = None, implement: Optional[str] = None, sources: Optional[sourcesDependency] = None) -> None:
        self.time = time
        self.headers = headers if headers else headersDependency(set(), set())
        self.modules = modules if modules else modulesDependency(
            set(), set(), set())
        self.provide = provide
        self.implement = implement
        self.sources = sources if sources else sourcesDependency(set())
        assert not provide or re.fullmatch(r"[\w.:]*", provide)
        assert time

    def __repr__(self) -> str:
        return str(vars(self))


class encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dependency):
            return vars(obj)
        elif isinstance(obj, modulesDependency):
            return vars(obj)
        elif isinstance(obj, headersDependency):
            return vars(obj)
        elif isinstance(obj, sourcesDependency):
            return vars(obj)
        elif isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


class extensionMapper:
    def __init__(self, headers: set[str], sources: set[str], head_source_pairs: dict[str, str]) -> None:
        self.headers = headers
        self.sources = sources
        self.head_source_pairs = head_source_pairs


# module name <--> relative path to root directory
global modulesBiDict
modulesBiDict: bidict[str, str] = bidict()
global content
content: str
global depsDict
depsDict: dict[str, dependency] = dict()
global depsDictCache
depsDictCache: dict[str, dependency] = dict()
global parDict
parDict: dict[str, set[str]] = dict()
# module name <--> reletive path of implement unit to root directory
global implDict
implDict: bidict[str, str] = bidict()

LOG_PATH = "umakeLog.txt"

global calculatedDependencies
calculatedDependencies: dict[str,
                             tuple[modulesDependency, sourcesDependency]] = dict()


def __collectDependencies(relFileToRoot: str, relRootToCur: str, verbosity: int, encoding: str, ext: extensionMapper, logUpdate: bool, touched: set[str]) -> tuple[modulesDependency, sourcesDependency]:
    if relFileToRoot in calculatedDependencies:
        return calculatedDependencies[relFileToRoot]
    relFileToCur = path.relpath(
        path.join(relRootToCur, relFileToRoot))
    newImported, newSources = recursiveCollectDependencies(
        relFileToCur, relRootToCur, verbosity, encoding, ext, logUpdate, touched)
    return newImported, newSources


def recursiveCollectDependencies(relSrcToCur: str, relRootToCur: str, verbosity: int, encoding: str, ext: extensionMapper, logUpdate: bool, touched: set[str]) -> tuple[modulesDependency, sourcesDependency]:
    try:
        relSrcToRoot = path.relpath(relSrcToCur, relRootToCur)

        relSrcDirToRoot = path.dirname(relSrcToRoot)

        assert relSrcToRoot not in touched, f"{relSrcToCur} indirectly dependended by itself."
        touched.add(relSrcToRoot)

        deps = depsDict[relSrcToRoot]
        importedModules = deps.modules
        dependedSources = deps.sources
        for relIncludedToSrc in depsDict[relSrcToRoot].headers.local:
            assert not path.isabs(relIncludedToSrc)
            relIncludedToRoot = path.relpath(
                path.join(relSrcDirToRoot, relIncludedToSrc))
            newImported, newSources = __collectDependencies(
                relIncludedToRoot, relRootToCur, verbosity, encoding, ext, logUpdate, touched)

            importedModules.unionWith(newImported)
            dependedSources.unionWith(newSources)
        if deps.provide != None:
            provide = deps.provide
            assert provide, "Oops!"
            for imported in deps.modules.module:
                if ':' in imported:
                    if imported.startswith(':'):
                        if ':' in provide:
                            provide = provide[provide.find(':'):]
                        imported = provide+':'+imported
                    assert imported in modulesBiDict, f"Importing {imported} from {relSrcToCur}, but it's not found."
                    relImportedToRoot = modulesBiDict[imported]
                    newImported, newSources = __collectDependencies(
                        relImportedToRoot, relRootToCur, verbosity, encoding, ext, logUpdate, touched)

                    importedModules.unionWith(newImported)
                    dependedSources.unionWith(newSources)
        if deps.implement != None:
            relInterfaceToRoot = modulesBiDict[deps.implement]
            newImported, newSources = __collectDependencies(
                relInterfaceToRoot, relRootToCur, verbosity, encoding, ext, logUpdate, touched)

            importedModules.unionWith(newImported)
            dependedSources.unionWith(newSources)
        for imported in deps.modules.module:
            relImportedToRoot = modulesBiDict[imported]
            newImported, newSources = __collectDependencies(
                relImportedToRoot, relRootToCur, verbosity, encoding, ext, logUpdate, touched)

            importedModules.unionWith(newImported)
            dependedSources.unionWith(newSources)

        calculatedDependencies[relSrcToRoot] = (
            importedModules, dependedSources)
        return importedModules, dependedSources
    except:
        print(YELLOW + f"In file {relSrcToCur}:" + RESET, file=stderr)
        raise


def scanAllFiles(relProjToCur: str, relRootToCur: str, excludeFiles: set[str], excludeDirs: set[str], encoding, extMapper: extensionMapper, moduleExtension: set[str], verbosity: int, logUpdate: bool) -> None:
    for dir, dirs, files in os.walk(relProjToCur):
        relDirToCur = path.relpath(dir)
        relDirToRoot = path.relpath(relDirToCur, relRootToCur)
        for excludeDir in excludeDirs:
            if path.exists(relDirToRoot) and path.exists(excludeDir) and path.samefile(relDirToRoot, excludeDir):
                if verbosity >= VERBOSITY_EXCLUDE_DIRECTORY:
                    print(
                        f"Walked-through dir \"{relDirToCur}\" is excluded as it matches \"{excludeDir}\"."
                    )
                continue
        for file in files:
            nothing, extName = path.splitext(file)
            relFileToCur = path.relpath(path.join(dir, file))
            relFileToRoot = path.relpath(relFileToCur, relRootToCur)
            for excludeFile in excludeFiles:
                if path.samefile(relFileToRoot, excludeFile):
                    if verbosity >= VERBOSITY_EXCLUDE_FILE:
                        print(
                            f"Walked-through file \"{relFileToCur}\" is excluded as it matches \"{excludeFile}\"."
                        )
                    continue
            if extName not in moduleExtension and extName not in extMapper.head_source_pairs.keys() and extName not in extMapper.head_source_pairs.values() and extName not in extMapper.headers and extName not in extMapper.sources:
                if verbosity >= VERBOSITY_EXCLUDE_FILE:
                    print(
                        f"Walked-through file \"{relFileToCur}\" has a different extension name, skipped."
                    )
                continue
            try:
                scanFileDependencies(relFileToCur, relRootToCur,
                                     verbosity, encoding, extMapper, logUpdate)
            except:
                print(f"In file {relFileToCur}:", file=stderr)
                raise


def scanFileDependencies(relSrcToCur: str, relRootToCur: str,  verbosity: int, encoding: str, ext: extensionMapper, logUpdate: bool) -> None:
    if "ast.ixx" in relSrcToCur:
        pass
    if not path.exists(relSrcToCur):
        raise Exception(
            f"Unexistent file \"{relSrcToCur}\" referenced.")

    relSrcToRoot = path.relpath(relSrcToCur, relRootToCur)
    relLog = path.relpath(path.join(relRootToCur, LOG_PATH))
    skip = False

    info: dependency
    if relSrcToRoot in depsDictCache:
        lastScanTime = depsDictCache[relSrcToRoot].time
        lastModTime = path.getmtime(relSrcToCur)
        if lastScanTime <= lastModTime:
            if verbosity >= VERBOSITY_MODIFIED_FILE:
                print(
                    BLUE + f"Modification after last scan detected on file \"{relSrcToCur}\"" + RESET)
            with open(relLog, 'a') as log:
                print(
                    f"{lastScanTime} < {lastModTime}, \"{relSrcToCur}\"",
                    file=log
                )
        else:
            if verbosity >= VERBOSITY_UNMODIFIED_FILE:
                print(
                    BLUE + f"Scanned file \"{relSrcToCur}\", skipped" + RESET)
            skip = True
    elif logUpdate:
        with open(relLog, 'a') as log:
            print(
                f"Missed, \"{relSrcToCur}\"",
                file=log
            )
    if skip:
        depsDict.update({relSrcToRoot: depsDictCache[relSrcToRoot]})
        info = depsDict[relSrcToRoot]
        if info.provide:
            modulesBiDict.update({info.provide: relSrcToRoot})
        if info.implement:
            implDict.update({info.implement: relSrcToRoot})
        return

    with open(relSrcToCur, encoding=encoding) as file:
        if verbosity >= VERBOSITY_SCANNING_FILE:
            print(BLUE + f"Scanning file \"{relSrcToCur}\"" + RESET)
        global content
        content = " " + file.read()

        def drop(next_index: int, desc: str):
            global content
            if verbosity >= VERBOSITY_DROPPING_FILE_CONTENT:
                print(CYAN+desc+RESET)
                print(content[:next_index])
            content = content[next_index+1:]
        info = dependency(time=time.time())

        relSrcSplitedHeadToCur, extName = path.splitext(relSrcToCur)
        if extName in ext.headers:
            for srcExtName in ext.sources:
                relSrcMappedSrcToCur = relSrcSplitedHeadToCur + srcExtName
                if path.exists(relSrcMappedSrcToCur):
                    info.sources.sources.add(
                        path.relpath(relSrcMappedSrcToCur, relRootToCur))
        if extName in ext.head_source_pairs.keys():
            mappedExt = ext.head_source_pairs[extName]
            relSrcMappedSrcToCur = relSrcSplitedHeadToCur + mappedExt
            if path.exists(relSrcMappedSrcToCur):
                info.sources.sources.add(
                    path.relpath(relSrcMappedSrcToCur, relRootToCur))

        while True:
            # Optimizable
            a, b, c, d, e, f, g, h = (content.find(s)
                                      for s in ["#include", '"', "'", '//', '/*', 'import', 'export', 'module'])

            if a == b == c == d == e == f == g == h == -1:
                depsDict[relSrcToRoot] = info
                if info.implement:
                    implDict.setdefault(info.implement, relSrcToRoot)
                if info.provide:
                    modulesBiDict.update({info.provide: relSrcToRoot})
                return

            if a == __uniqueMin(a, b, c, d, e, f, g, h):  # include
                content = content[a+len("#include"):]
                content = content.lstrip()
                lib = re.search(r"^<[^<>]*>", content)
                loc = re.search(r'^"[^"]*"', content)
                if lib:
                    span = lib.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= VERBOSITY_INCLUDING_HEADER:
                        print(BLUE + "Including library header "+_path + RESET)
                    content = content[span[1]:]
                    info.headers.library.add(_path[1:-1])
                elif loc:
                    span = loc.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= VERBOSITY_INCLUDING_HEADER:
                        print(BLUE + "Including local header "+_path + RESET)
                    content = content[span[1]:]
                    info.headers.local.add(_path[1:-1])
                else:
                    raise Exception("What's being included?")
            elif b == __uniqueMin(a, b, c, d, e, f, g, h):  # string
                raw = content[b-1] == 'R'  # Check if is raw string literal
                content = content[b+1:]
                if raw:
                    end = ')'+content[:content.find("(")]+'"'
                else:
                    end = '"'

                while True:
                    escape = content.find("\\")
                    next_quote = content.find(end)
                    assert next_quote != -1, "Quotes not matched."
                    if raw or escape < 0 or escape > next_quote:
                        break
                    assert (
                        linesep not in content[:escape + 1]
                        or raw
                    ), "Multiline string"
                    drop(escape+1, "Dropping below in escaped string:")
                assert (
                    linesep not in content[:next_quote + 1]
                    or raw
                ), "Multiline string"
                drop(next_quote+1, "Dropping below in escaped string:")
            elif c == __uniqueMin(a, b, c, d, e, f, g, h):  # character
                content = content[c+1:]
                while True:
                    escape = content.find("\\")
                    next_quote = content.find(r"'")
                    assert next_quote != -1, "Quotes not matched."
                    if escape == -1 or escape > next_quote:
                        break
                    drop(escape+1, "Dropping below in eacaped string:")

                assert linesep not in content[:next_quote +
                                              1], "Multiline character"
                drop(next_quote, "Dropping below in character:")
            elif d == __uniqueMin(a, b, c, d, e, f, g, h):  # comment //
                content = content[d:]
                endline = content.find('\n\r')
                if endline == -1:
                    endline = content.find('\r\n')
                if endline == -1:
                    endline = content.find('\n')
                if endline == -1:
                    endline = content.find('\r')
                if endline == -1:
                    drop(len(content)-1, "Drropping below in comment:")
                else:
                    drop(endline-1, "Dropping below in comment:")
            elif e == __uniqueMin(a, b, c, d, e, f, g, h):  # comment /**/
                content = content[e:]
                end_note = content.find('*/')
                drop(end_note+len('*/'), "Dropping below in multi-line comment:")
            elif f == __uniqueMin(a, b, c, d, e, f, g, h):  # import
                if f == 0 or (f > 0 and re.fullmatch(r'\w', content[f-1])):
                    content = content[h+len("import")-1:]
                    continue
                content = content[f+len("import"):]
                if re.fullmatch(r"\w", content[0]):
                    continue
                next = re.search(r"[^\s]", content)
                assert next, "Unexpected termination."
                content = content[next.span()[0]:]
                import_begin = 0
                # Does it possible to have a semicolon in the name of a imported header?
                import_end = content.find(r';')
                assert import_end != -1, "Unexpected termination after 'import'"
                imported = content[import_begin:import_end]
                imported = __removeSpace(imported)
                if re.fullmatch(r"<[^<>]*>", imported):
                    info.modules.library.add(imported)
                elif re.fullmatch(r"\"[^\"]*\"", imported):
                    info.modules.local.add(imported)
                elif re.fullmatch(r"[\w.:]+", imported):
                    if imported.startswith(":"):
                        main: str | None = info.provide if info.provide else info.implement
                        assert main, "Importing partition should be written after module declaration or implementation."
                        if ":" in main:
                            semicolon = main.rfind(":")
                            main = main[:semicolon]
                        parDict.setdefault(main, set())
                        parDict[main].add(imported)
                        info.modules.module.add(main+imported)
                    else:
                        info.modules.module.add(imported)
                else:
                    raise Exception("What's being imported?")

                content = content[import_end+1:]
            elif g == __uniqueMin(a, b, c, d, e, f, g, h):  # export
                if g == 0 or (g > 0 and re.fullmatch(r'\w', content[g-1])):
                    content = content[h+len("export"):]
                    continue
                content = content[g+len("export"):]
                if re.fullmatch(r"\w", content[0]):
                    continue
                next = re.search(r"[^\s]", content)
                assert next, "Unexpected termination."
                content = content[next.span()[0]:]
                semicolon = None
                if content.startswith("module"):
                    assert not info.provide, "Exporting more than 1 modules"
                    content = content.removeprefix("module")
                    semicolon = content.find(";")
                    info.provide = __removeSpace(content[:semicolon])
                elif content.startswith("import"):
                    assert info.provide, "Re-exporting should be written after exporting."
                    content = content.removeprefix("import")
                    semicolon = content.find(";")
                    partition = __removeSpace(content[:semicolon])
                    parDict.setdefault(info.provide, set())
                    parDict[info.provide].add(partition)
                    info.modules.module.add(info.provide+partition)
                else:
                    if verbosity >= VERBOSITY_EXPORTING:
                        print(CYAN + "Exporting" + RESET)

                if semicolon:
                    content = content[semicolon+1:]
            elif h == __uniqueMin(a, b, c, d, e, f, g, h):  # module
                if h == 0 or (h > 0 and re.fullmatch(r'\w', content[h-1])):
                    content = content[h+len("module")-1:]
                    continue
                content = content[h+len("module"):]
                if re.fullmatch(r"\w", content[0]):
                    continue
                next = re.search(r"[^\s]", content)
                assert next, "Unexpected termination."
                content = content[next.span()[0]:]
                semicolon = content.find(";")
                implement = __removeSpace(content[:semicolon])
                if re.fullmatch(r"\s*", implement):
                    continue
                info.implement = implement

                content = content[semicolon+1:]
            else:
                raise Exception("What the fuck?")


CACHE_PATH = "umakeCache.json"


def saveCache(relRootToCur: str):
    with open(path.join(relRootToCur, CACHE_PATH), 'w') as cache:
        json.dump(depsDict, cache, cls=encoder)


def deleteCache(relRootToCur: str):
    relCacheToCur = path.relpath(path.join(relRootToCur, CACHE_PATH))
    if path.exists(relCacheToCur):
        os.remove(relCacheToCur)
        print(YELLOW+f"Root is \"{relRootToCur}\"."+RESET, file=stderr)
        print(YELLOW+f"Cache at \"{relCacheToCur}\" deleted." +
              RESET, file=stderr)
    else:
        print(YELLOW+"Cache not found."+RESET, file=stderr)


def loadCache(relRootToCur: str):
    relCacheToCur = path.relpath(path.join(relRootToCur, CACHE_PATH))
    if path.exists(relCacheToCur):
        try:
            with open(relCacheToCur) as cache:
                s: dict[
                    str, dict[str,
                              Any
                              # Union[str, dict[str, list[str]]]
                              ]
                ] = json.load(cache)
                for source, dep in s.items():
                    headers: dict[str, list[str]] = dep["headers"]
                    modules: dict[str, list[str]] = dep["modules"]
                    sources: dict[str, list[str]] = dep["sources"]
                    depsDictCache.update({source: dependency(
                        dep["time"],
                        headersDependency(
                            set(headers["library"]), set(headers["local"])
                        ),
                        modulesDependency(
                            set(modules["module"]),
                            set(modules["library"]),
                            set(modules["local"])
                        ),
                        dep["provide"],
                        dep["implement"],
                        sourcesDependency(set(sources["sources"]))
                    )})
        except Exception as e:
            print("Original cache is not correct for reason below. Deleting.")
            print(e)
            os.remove(relCacheToCur)


def cleanCache():
    depsDictCache = None
