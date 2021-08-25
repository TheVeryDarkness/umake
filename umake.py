"""
A minimal build tool for c++.
Do not write coded like below to confuse me,
especially when importing that would cause errors:

# if 0
import somemodule;
# endif
"""
import argparse
from bidict import bidict
from colorama import Fore, init
import os.path as path
import os
import re
from typing import Union

init()
GREEN = Fore.GREEN
BLUE = Fore.BLUE
CYAN = Fore.CYAN
YELLOW = Fore.YELLOW
RED = Fore.RED
RESET = Fore.RESET
linesep = '\n'


def unique_min(*numbers: int):
    res = min(*numbers)
    assert numbers.count(res) == 1
    return res


# module name <--> relative path to current directory
global modulesBiDict
modulesBiDict = bidict()


def recursiveScanLocalDependencies(relSrcToCur: str, relRootToCur: str, depsDict: dict, verbosity: int, encoding: str) -> list[set[str], set[str]]:
    try:
        relSrcToRoot = path.relpath(relSrcToCur, relRootToCur)
        if relSrcToRoot in depsDict:
            if verbosity >= 2:
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
                path.join(relRoot, relIncludedToRoot))
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

            if a == unique_min(a, b, c, d, e, f, g):
                content = content[a+len("#include"):]
                next = re.search("[^\s]", content)
                content = content[next.span()[0]:]
                lib = re.search(r"^<[^<>]*>", content)
                loc = re.search(r'^"[^"]*"', content)
                if lib:
                    span = lib.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= 3:
                        print(BLUE + "Including library header "+_path + RESET)
                    content = content[span[1]+1:]
                    info[0].append(_path[1:-1])
                elif loc:
                    span = loc.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= 3:
                        print(BLUE + "Including local header "+_path + RESET)
                    content = content[span[1]+1:]
                    info[1].append(_path[1:-1])
                else:
                    raise Exception("What's being included?")
            elif b == unique_min(a, b, c, d, e, f, g):
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
            elif c == unique_min(a, b, c, d, e, f, g):
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
            elif d == unique_min(a, b, c, d, e, f, g):
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
            elif e == unique_min(a, b, c, d, e, f, g):
                content = content[:e]
                end_note = content.find('*/')
                drop(end_note+len('*/'), "Dropping below in multi-line comment:")
            elif f == unique_min(a, b, c, d, e, f, g):
                content = content[f+len("import"):]
                next = re.search(r"[^\s]", content)
                assert next, "Unexpected termination."
                content = content[next.span()[0]:]
                import_begin = 0
                # Does it possible to have a semicolon in the name of a imported header?
                import_end = re.search(r';', content).span()[0]
                imported = content[import_begin:import_end]
                imported.strip()
                if re.fullmatch(r"<[^<>]*>", imported):
                    info[2].append(imported)
                elif re.fullmatch(r"\"[^\"]*\"", imported):
                    info[3].append(imported)
                elif re.fullmatch(r"[\w.:]+", imported):
                    info[4].append(imported)
                else:
                    raise Exception("What's being imported?")
            elif g == unique_min(a, b, c, d, e, f, g):
                content = content[g+len("export"):]
                next = re.search(r"[^\s]", content)
                assert next, "Unexpected termination."
                content = content[next.span()[0]:]
                if content.startswith("module"):
                    assert len(info[5]) == 0, "Exporting more than 1 modules"
                    content = content.removeprefix("module")
                    content = content.lstrip()
                    semicolon = content.find(";")
                    info[5].append(content[:semicolon])
                elif content.startswith("import"):
                    assert len(
                        info[5]) != 0, "Re-exporting should be written after exporting."
                    content = content.removeprefix("import")
                    content = content.lstrip()
                    semicolon = content.find(";")
                    partition = content[:semicolon]
                    info[2].append(info[5][0]+partition)
                else:
                    if verbosity >= 5:
                        print(CYAN + "Exporting" + RESET)
            else:
                raise


if __name__ == "__main__":
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
    depsDict = dict()
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
                    if verbosity >= 3:
                        print(
                            "Walked-through file \"{}\" has a different extension name, skipped.".format(relFileToCur))
                    continue
                if relFileToRoot not in depsDict:
                    modulesToBePreCompiledByEachSource[source] = recursiveScanLocalDependencies(
                        relFileToCur, relRoot, depsDict, verbosity, encoding)
        for _source, modulesToBePreCompiled in modulesToBePreCompiledByEachSource.items():
            for moduleToBePreCompiled in modulesToBePreCompiled[2]:
                if moduleToBePreCompiled not in modulesBiDict:
                    print(
                        YELLOW+"Imported module \"{}\" is not found from dependencies of{}".format(moduleToBePreCompiled, _source)+RESET)
        if target == "dict":
            print(GREEN + str(modulesToBePreCompiledByEachSource) + RESET)
            print(GREEN + str(modulesBiDict) + RESET)
        else:
            raise Exception("Unknown target")
    except Exception as e:
        print('\t', RED + str(e) + RESET, sep="")
        print(RED + "Failed for parsed arguments: {}.".format(args) + RESET)
