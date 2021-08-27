"""
A minimal dependencies scanning tool for c++ under MIT license.
Written by TheVeryDarkness, 1853308@tongji.edu.cn on Github.
"""
from __future__ import annotations
from sys import stderr

from typing import Optional, Union
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


def __removeSpace(s: str):
    return s.strip().replace(' ', '').replace('\t', '')


def __uniqueMin(*numbers: int):
    res = min(*numbers)
    assert numbers.count(res) == 1
    return res


class headersDependency:
    def __init__(self, library: set[str], local: set[str]) -> None:
        self.local = local
        self.library = library

    def __len__(self) -> int:
        return sum([0 if len(self.__dict__[key]) == 0 else 1 for key in ["local", "library"]])

    def __repr__(self) -> str:
        res = dict()
        for key in ["library", "local"]:
            if self.__dict__[key] and len(self.__dict__[key]) != 0:
                res.update({key: self.__dict__[key]})
        return str(res)


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

    def __repr__(self) -> str:
        res = dict()
        for key in ["module", "library", "local"]:
            if self.__dict__[key] and len(self.__dict__[key]) != 0:
                res.update({key: self.__dict__[key]})
        return str(res)


class dependency:
    def __init__(self, headers: Optional[headersDependency] = None, modules: Optional[modulesDependency] = None, provided: Optional[str] = None, time: Optional[float] = None) -> None:
        self.headers = headers if headers else headersDependency(set(), set())
        self.modules = modules if modules else modulesDependency(
            set(), set(), set())
        self.provided = provided
        self.time = time
        assert not provided or re.fullmatch("[\w.:]*", provided)
        assert time

    def __repr__(self) -> str:
        res = dict()
        for key in ["headers", "modules", "provided", "time"]:
            if self.__dict__[key] and len(self.__dict__[key]) != 0:
                res.update({key: self.__dict__[key]})
        return str(res)


class encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dependency):
            return {"headers": obj.headers, "modules": obj.modules, "provided": obj.provided, "time": obj.time}
        elif isinstance(obj, modulesDependency):
            return {"module": obj.module, "library": obj.library, "local": obj.local}
        elif isinstance(obj, headersDependency):
            return {"library": obj.library, "local": obj.local}
        elif isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


# module name <--> relative path to current directory
global modulesBiDict
modulesBiDict: bidict[str, str] = bidict()
global content
content: str
global depsDict
depsDict: dict[str, dependency] = dict()


def recursiveScanLocalDependencies(relSrcToCur: str, relRootToCur: str, verbosity: int, encoding: str) -> modulesDependency:
    try:
        relSrcToRoot = path.relpath(relSrcToCur, relRootToCur)
        skip = False
        if relSrcToRoot in depsDict:
            if time.time() > path.getmtime(relSrcToCur):
                if verbosity >= 2:
                    print(
                        BLUE + "Modification after last scan detected on file \"{}\"".format(relSrcToCur) + RESET)
                skip = True
            else:
                if verbosity >= 3:
                    print(
                        BLUE + "Scanned file \"{}\", skipped".format(relSrcToCur) + RESET)
        if not skip:
            depsDict[relSrcToRoot] = scanFileDependencies(
                relSrcToCur, verbosity, encoding)
        relSrcDirToRoot = path.dirname(relSrcToRoot)
        imported = depsDict[relSrcToRoot].modules
        exported = depsDict[relSrcToRoot].provided
        if exported:
            modulesBiDict.update({exported: relSrcToRoot})
        for relIncludedToSrc in depsDict[relSrcToRoot].headers.local:
            assert not path.isabs(relIncludedToSrc)
            relIncludedToRoot = path.relpath(
                path.join(relSrcDirToRoot, relIncludedToSrc))
            relIncludedToCur = path.relpath(
                path.join(relRootToCur, relIncludedToRoot))
            newDeps = recursiveScanLocalDependencies(
                relIncludedToCur, relRootToCur, verbosity, encoding)

            imported.unionWith(newDeps)
        return imported
    except:
        print(YELLOW + "In file {}:".format(relSrcToCur) + RESET, stderr)
        raise


def scanFileDependencies(filename: str, verbosity: int, encoding: str) -> dependency:
    if not path.exists(filename):
        raise Exception("Unexistent file \"{}\" referenced.".format(filename))
    with open(filename, encoding=encoding) as file:
        if verbosity >= 1:
            print(BLUE + "Scanning file \"{}\"".format(filename) + RESET)
        global content
        content = file.read()

        def drop(next_index: int, desc: str):
            global content
            if verbosity >= 6:
                print(CYAN+desc+RESET)
                print(content[:next_index])
            content = content[next_index+1:]
        info: dependency = dependency(time=time.time())
        while True:
            # Optimizable
            a, b, c, d, e, f, g = (content.find(s)
                                   for s in ["#include", '"', "'", '//', '/*', 'import', 'export'])

            if a == b == c == d == e == f == g == -1:
                return info
            if a == -1:
                a = len(content)
            if b == -1:
                b = len(content)
            if c == -1:
                c = len(content)
            if d == -1:
                d = len(content)
            if e == -1:
                e = len(content)
            if f == -1:
                f = len(content)
            if g == -1:
                g = len(content)

            if a == __uniqueMin(a, b, c, d, e, f, g):
                content = content[a+len("#include"):]
                content = content.lstrip()
                lib = re.search(r"^<[^<>]*>", content)
                loc = re.search(r'^"[^"]*"', content)
                if lib:
                    span = lib.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= 4:
                        print(BLUE + "Including library header "+_path + RESET)
                    content = content[span[1]+1:]
                    info.headers.library.add(_path[1:-1])
                elif loc:
                    span = loc.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= 4:
                        print(BLUE + "Including local header "+_path + RESET)
                    content = content[span[1]+1:]
                    info.headers.local.add(_path[1:-1])
                else:
                    raise Exception("What's being included?")
            elif b == __uniqueMin(a, b, c, d, e, f, g):
                content = content[b+1:]
                while True:
                    escape = content.find("\\")
                    next_quote = content.find(r'"')
                    assert next_quote != -1, "Quotes not matched."
                    if escape == -1 or escape > next_quote:
                        break
                    drop(escape+1, "Dropping below in escaped string:")

                assert linesep not in content[:next_quote +
                                              1], "Multiline string"
                drop(next_quote, "Dropping below in string:")
            elif c == __uniqueMin(a, b, c, d, e, f, g):
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
            elif d == __uniqueMin(a, b, c, d, e, f, g):
                content = content[:d]
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
                    drop(endline, "Dropping below in comment:")
            elif e == __uniqueMin(a, b, c, d, e, f, g):
                content = content[:e]
                end_note = content.find('*/')
                drop(end_note+len('*/'), "Dropping below in multi-line comment:")
            elif f == __uniqueMin(a, b, c, d, e, f, g):
                content = content[f+len("import"):]
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
                    info.modules.module.add(imported)
                else:
                    raise Exception("What's being imported?")
            elif g == __uniqueMin(a, b, c, d, e, f, g):
                content = content[g+len("export"):]
                next = re.search(r"[^\s]", content)
                assert next, "Unexpected termination."
                content = content[next.span()[0]:]
                if content.startswith("module"):
                    assert not info.provided, "Exporting more than 1 modules"
                    content = content.removeprefix("module")
                    semicolon = content.find(";")
                    info.provided = __removeSpace(content[:semicolon])
                elif content.startswith("import"):
                    assert info.provided, "Re-exporting should be written after exporting."
                    content = content.removeprefix("import")
                    semicolon = content.find(";")
                    partition = content[:semicolon]
                    info.modules.module.add(
                        info.provided + __removeSpace(partition))
                else:
                    if verbosity >= 5:
                        print(CYAN + "Exporting" + RESET)
            else:
                raise


CACHE_PATH = "umakeCache.json"


def save(relRootToCur: str):
    with open(path.join(relRootToCur, CACHE_PATH), 'w') as cache:
        json.dump(depsDict, cache, cls=encoder)


def load(relRootToCur: str):
    relCacheToCur = path.relpath(path.join(relRootToCur, CACHE_PATH))
    if path.exists(relCacheToCur):
        try:
            with open(relCacheToCur) as cache:
                s: dict[str, dict[str, Union[str, list[str]]]
                        ] = json.load(cache)
                for source, dep in s.items():
                    depsDict.update({source: dependency(
                        headersDependency(set(dep["headers"]["library"]), set(
                            dep["headers"]["local"])),
                        modulesDependency(set(dep["modules"]["module"]), set(
                            dep["modules"]["library"]), set(dep["modules"]["local"])),
                        dep["provided"],
                        dep["time"])})
        except Exception as e:
            print("Original cache is not correct for reason below. Deleting.")
            print(e)
            os.remove(relCacheToCur)
