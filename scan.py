"""
A minimal dependencies scanning tool for c++ under MIT license.
Written by TheVeryDarkness, 1853308@tongji.edu.cn on Github.
"""
from bidict import bidict
from colorama import Fore, init
import os.path as path
import os
import re

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


# module name <--> relative path to current directory
global modulesBiDict
modulesBiDict: bidict = bidict()
global content
content: str


def recursiveScanLocalDependencies(relSrcToCur: str, relRootToCur: str, depsDict: dict, verbosity: int, encoding: str) -> list[set[str]]:
    try:
        relSrcToRoot = path.relpath(relSrcToCur, relRootToCur)
        if relSrcToRoot in depsDict:
            if verbosity >= 3:
                print(BLUE + "Scanned file \"{}\", skipped".format(relSrcToCur) + RESET)
        else:
            depsDict[relSrcToRoot] = scanFileDependencies(
                relSrcToCur, verbosity, encoding)
        relSrcDirToRoot = path.dirname(relSrcToRoot)
        imported = [set(depsDict[relSrcToRoot][i]) for i in range(2, 5)]
        exported = depsDict[relSrcToRoot][5]
        if exported:
            assert len(exported) == 1
            modulesBiDict.update({exported[0]: relSrcToRoot})
        for relIncludedToSrc in depsDict[relSrcToRoot][1]:
            assert not path.isabs(relIncludedToSrc)
            relIncludedToRoot = path.relpath(
                path.join(relSrcDirToRoot, relIncludedToSrc))
            relIncludedToCur = path.relpath(
                path.join(relRootToCur, relIncludedToRoot))
            newDeps = recursiveScanLocalDependencies(
                relIncludedToCur, relRootToCur, depsDict, verbosity, encoding)

            for i in range(3):
                imported[i] = imported[i].union(newDeps[i])
        return imported
    except:
        print(YELLOW + "In file {}:".format(relSrcToCur) + RESET)
        raise


def scanFileDependencies(filename: str, verbosity: int, encoding: str) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str]]:
    '''
    0 list: Included global headers
    1 list: Included local headers
    2 list: Imported modules
    3 list: Imported global headers (Legacy)
    4 list: Imported local headers (Legacy)
    5 str|None: Exported Module
    '''
    if not path.exists(filename):
        raise Exception("Unexistent file {} referenced.".format(filename))
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
        info: tuple[list[str], list[str], list[str], list[str],
                    list[str], list[str]] = ([], [], [], [], [], [])
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
                    info[0].append(_path[1:-1])
                elif loc:
                    span = loc.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= 4:
                        print(BLUE + "Including local header "+_path + RESET)
                    content = content[span[1]+1:]
                    info[1].append(_path[1:-1])
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
                    info[2].append(imported)
                elif re.fullmatch(r"\"[^\"]*\"", imported):
                    info[3].append(imported)
                elif re.fullmatch(r"[\w.:]+", imported):
                    info[4].append(imported)
                else:
                    raise Exception("What's being imported?")
            elif g == __uniqueMin(a, b, c, d, e, f, g):
                content = content[g+len("export"):]
                next = re.search(r"[^\s]", content)
                assert next, "Unexpected termination."
                content = content[next.span()[0]:]
                if content.startswith("module"):
                    assert len(info[5]) == 0, "Exporting more than 1 modules"
                    content = content.removeprefix("module")
                    semicolon = content.find(";")
                    info[5].append(__removeSpace(content[:semicolon]))
                elif content.startswith("import"):
                    assert len(
                        info[5]) != 0, "Re-exporting should be written after exporting."
                    content = content.removeprefix("import")
                    semicolon = content.find(";")
                    partition = content[:semicolon]
                    info[2].append(info[5][0] + __removeSpace(partition))
                else:
                    if verbosity >= 5:
                        print(CYAN + "Exporting" + RESET)
            else:
                raise

