# Communicate with cmake
from config import *
from scan import *
from typing import TextIO


def write_cmake(
    out: TextIO,
    modulesToBePreCompiledBySources: dict[str, modulesDependency],
    objectsDict: bidict[str, str],
    extraSourcesBySources: dict[str, sourcesDependency],
):

    built: list[str] = []
    while len(built) < len(modulesToBePreCompiledBySources):
        has_built_one_in_one_loop = False
        for source, modules in modulesToBePreCompiledBySources.items():
            depend = False
            reference = False
            if source in built or any(
                [modulesBiDict[module] not in built for module in modules.module]
            ):
                # Dependencies not built or already built
                continue
            if (
                source in implDict.inverse
                and modulesBiDict[implDict.inverse[source]] not in built
            ):
                # Module implement's corresponding interface not built
                continue

            has_built_one_in_one_loop = True
            if source in modulesBiDict.inverse:
                out.write(f"MODULE {modulesBiDict.inverse[source]} ")
            elif source in relSourcesToRoot:
                out.write(f"TARGET {targetsBidict.inverse[source]} ")
            elif source in implDict.inverse:
                out.write(f"IMPLEMENT {implDict.inverse[source]} ")
            else:
                if not autoObj:
                    continue
                out.write(f"OBJECT {objectsDict[source]} ")
            out.write(f"SOURCE {source} ")
            if source in modulesBiDict.inverse:
                if modulesBiDict.inverse[source] in implDict.keys():
                    out.write(f"IMPLEMENT ")

            for extraSourcesBySource in extraSourcesBySources[source].sources:
                if extraSourcesBySource == source:
                    continue
                if not depend:
                    out.write(f"DEPEND ")
                    depend = True
                out.write(f"{objectsDict[extraSourcesBySource]}")
            for module in modules.module:
                if module in modulesBiDict.keys():
                    if not reference:
                        out.write(f"REFERENCE ")
                        reference = True
                    out.write(f"{module} ")
                    if module in parDict:
                        for par in parDict[module]:
                            out.write(f"{module + par} ")
            built.append(source)
            if len(built) < len(modulesToBePreCompiledBySources):
                out.write(";\n")

        assert has_built_one_in_one_loop, "Cyclic imports among {}.".format(
            set(modulesToBePreCompiledBySources.keys()) - set(built)
        )
