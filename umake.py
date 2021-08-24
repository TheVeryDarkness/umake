"""
A minimal build tool for c++.
Do not write coded like below to confuse me,
especially when importing that would cause errors:

#if 0
import somemodule;
#endif
"""
from genericpath import isdir
import os.path as path
import argparse
from posixpath import isabs
import re
from typing import Union


def unique_min(*numbers: int):
    res = min(*numbers)
    assert numbers.count(res) == 1
    return res


def recursiveScanLocalDependencies(relSrcToCur: str, relRootToCur: str, depsDict: dict, verbosity: int, encoding: str) -> tuple[list, list]:
    try:
        relSrcToRoot = path.join(relSrcToCur, relRootToCur)
        if relSrcToRoot in depsDict:
            if verbosity >= 2:
                print("Scanned file \"{}\", skipped".format(relSrcToCur))
            return ()
        depsDict[relSrcToRoot] = scanFileDependencies(
            relSrcToCur, verbosity, encoding)
        relSrcDirToRoot = path.dirname(relSrcToRoot)
        for relIncludedToSrc in depsDict[relSrcToRoot][1]:
            assert not isabs(relIncludedToSrc)
            relIncludedToRoot = path.relpath(
                path.join(relSrcDirToRoot, relIncludedToSrc))
            relIncludedToCur = path.relpath(
                path.join(relRoot, relIncludedToRoot))
            recursiveScanLocalDependencies(
                relIncludedToCur, relRootToCur, depsDict, verbosity, encoding)
    except:
        print("In file {}:".format(relSrcToCur))
        raise


def scanFileDependencies(filename: str, verbosity: int, encoding: str) -> tuple[list[str], list[str], list[str], list[str], list[str], Union[str, None]]:
    '''
    list: Included global headers
    list: Included local headers
    list: Imported modules
    list: Imported global headers (Legacy)
    list: Imported local headers (Legacy)
    str|None: Exported Module
    '''
    if not path.exists(filename):
        raise Exception("Unexistent file {} referenced.".format(filename))
    with open(filename, encoding=encoding) as file:
        if verbosity >= 1:
            print("Scanning file \"{}\"".format(filename))
        content = file.read()
        info = ([], [], [], [], [], None)
        while True:
            # Optimizable
            a, b, c, d = (content.find(s)
                          for s in ["#include", '"', 'import', 'export'])

            if a == b == c == d == -1:
                return info
            if a == -1:
                a = len(content)
            if b == -1:
                b = len(content)
            if c == -1:
                c = len(content)
            if d == -1:
                d = len(content)

            if a == unique_min(a, b, c, d):
                content = content[a+len("#include"):]
                next = re.search("[^\s]", content)
                content = content[next.span()[0]:]
                lib = re.search(r"^<[^<>]*>", content)
                loc = re.search(r'^"[^"]*"', content)
                if lib:
                    span = lib.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= 3:
                        print("Including library header "+_path)
                    content = content[span[1]+1:]
                    info[0].append(_path[1:-1])
                elif loc:
                    span = loc.span()
                    _path = content[span[0]:span[1]]
                    if verbosity >= 3:
                        print("Including local header "+_path)
                    content = content[span[1]+1:]
                    info[1].append(_path[1:-1])
                else:
                    raise Exception("What's being included?")
            elif b == unique_min(a, b, c, d):
                content = content[b+1:]
                next_quote = re.search(r'(?<!\\)"', content).span()[0]
                content = content[next_quote+1:]
            elif c == unique_min(a, b, c, d):
                content = content[c+len("import"):]
                next = re.search(r"[^\s]", content)
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

            elif d == unique_min(a, b, c, d):
                pass
            else:
                raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", metavar="source", nargs="+",
                        type=str, help="The main source file to compile and link to.")
    parser.add_argument("-P", "--project", type=str,
                        help="The path to thr source file folder for the project. Every file in this folder may be scanned for module, especially if the project uses import.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="More verbose output.")
    parser.add_argument("-r", "--root", type=str,
                        help="The root path to generate build file, such as makefile or scripts.")
    parser.add_argument("-t", "--target", type=str,
                        default="dict", help="The target format of build file.")
    parser.add_argument("-e", "--encoding", type=str,
                        default="UTF-8", help="The encoding of source files.")
    args = parser.parse_args()

    sources: list[str] = args.sources
    verbosity: int = args.verbose
    root: str = args.root
    target: str = args.target
    encoding: str = args.encoding

    assert isdir(root)
    relRoot = path.relpath(root)
    depsDict = dict()
    try:
        for source in sources:
            imports = recursiveScanLocalDependencies(
                source, relRoot, depsDict, verbosity, encoding)
        if target == "dict":
            print(str(depsDict))
        else:
            raise Exception("Unknown target")
    except Exception as e:
        print('\t', e, sep="")
        print("Failed for parsed arguments: {}.".format(args))
