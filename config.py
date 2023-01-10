import argparse
from bidict import bidict
import json
import os.path as path
from sys import argv

CONFIG_PATH = "umakeConfig.json"


def loadConfig(args: argparse.Namespace, relRoot: str, default: argparse.Namespace):
    configPath = path.join(args.root, CONFIG_PATH)
    if not path.exists(configPath):
        return
    with open(configPath) as config:
        cfg = json.load(config)
        for key, value in cfg.items():
            if (
                key not in vars(args).keys()
                or key not in vars(default).keys()
                or vars(args)[key] == vars(default)[key]
            ):
                vars(args)[key] = value
        if "sources" in cfg.keys():
            for i in range(len(cfg["sources"]) // 2):
                sources = cfg["sources"]
                sources[2 * i + 1] = path.relpath(
                    path.join(relRoot, path.relpath(sources[2 * i + 1]))
                )


def saveConfig(args: argparse.Namespace):
    vars(args)["umake.py"] = argv[0]
    vars(args)["root"] = path.relpath(vars(args)["root"])
    vars(args)["folders"] = [path.relpath(folder) for folder in vars(args)["folders"]]
    with open(path.join(args.root, CONFIG_PATH), "w") as config:
        json.dump(vars(args), config)


parser = argparse.ArgumentParser()
parser.add_argument(
    "sources",
    nargs="*",
    type=str,
    help="The main target and its source file to compile and link to.",
)
parser.add_argument(
    "-v",
    "--verbose",
    action="count",
    default=0,
    help="Verbosity level. Repeat this option to increase.",
)
parser.add_argument(
    "-r",
    "--root",
    type=str,
    help="The root path to generate build file, such as makefile or scripts. Current working directory by default.",
)
parser.add_argument(
    "-f",
    "--folders",
    type=str,
    nargs="*",
    help="The paths to the source file folders. Every file in those folders may be scanned. Root by default.",
)
parser.add_argument("-t", "--target", type=str, help="The target format of output.")
parser.add_argument(
    "-M",
    "--module",
    type=str,
    nargs="+",
    default=[".ixx", ".mpp", ".cppm"],
    help="Possible extension names of cpp module interface files. Other files will be skipped during modules scanning.",
)
parser.add_argument(
    "-e",
    "--encoding",
    type=str,
    default="UTF-8",
    help="The encoding of source files.",
)
parser.add_argument(
    "-Ed",
    "--exclude-dirs",
    action="append",
    default=[],
    type=str,
    help="Folders to be excluded. Treated as regex.",
)
parser.add_argument(
    "-Ef",
    "--exclude-files",
    action="append",
    default=[],
    type=str,
    help="Files to be excluded. Treated as regex.",
)
parser.add_argument(
    "--no-auto-obj", action="store_true", help="Turn off object dependency output."
)
parser.add_argument("-c", "--cc", type=str, help="C compiler.")
parser.add_argument("-C", "--cxx", type=str, help="C++ compiler.")
parser.add_argument(
    "-eh", "--ext-header", nargs="*", default=[], help="Extension names of headers."
)
parser.add_argument(
    "-es", "--ext-source", nargs="*", default=[], help="Extension names of sources."
)
parser.add_argument(
    "-ehs",
    "--ext-header-source",
    nargs=2,
    default=[[".hh", ".cc"], [".hpp", ".cpp"], [".h", ".c"]],
    help="Extension name pairs of header and sources. Only corresponding sources of scanned headers will be added to object dependencies.",
)
parser.add_argument(
    "--save-config",
    action="store_true",
    help="Ask umake to generate umakeConfig.json and save configurations.",
)
parser.add_argument(
    "--load-config",
    action="store_true",
    help="Ask umake to read and load umakeConfig.json on root. Configuration will be preferred unless not given.",
)
parser.add_argument("--no-cache", action="store_true", help="Disable scanning caches")
parser.add_argument(
    "--log-update", action="store_true", help="Log when cache is updated."
)
args = parser.parse_args()
default = parser.parse_args([])
_loadConfig = args.load_config
_saveConfig = args.save_config

assert "root" in vars(args), "Specify the output dir, please."
root: str = args.root
assert path.isdir(root)
relRoot = path.relpath(root)

if _loadConfig:
    loadConfig(args, relRoot, default)

if not args.folders:
    args.folders = [args.root]

if _saveConfig:
    saveConfig(args)

assert len(args.sources) % 2 == 0, "Target should match source"
target_source_pairs: list[tuple[str, str]] = [
    (args.sources[2 * i], path.relpath(args.sources[2 * i + 1], relRoot))
    for i in range(len(args.sources) // 2)
]
targetsBidict: bidict[str, str] = bidict(target_source_pairs)
# target <--> source
sources: list[str] = [
    path.relpath(args.sources[2 * i + 1]) for i in range(len(args.sources) // 2)
]
relSourcesToRoot = [path.relpath(relSourceToCur, relRoot) for relSourceToCur in sources]
verbosity: int = args.verbose
target: str = args.target
encoding: str = args.encoding
folders: list[str] = args.folders
relFoldersToCur = [
    path.relpath(path.join(relRoot, path.relpath(folder))) for folder in folders
]
moduleExtension: list[str] = args.module
excludeFiles = args.exclude_files
excludeDirs = args.exclude_dirs
cacheDisabled: bool = args.no_cache
logUpdate: bool = args.log_update

relOutToRoot: str
if "output" in args:
    relOutToRoot = args.output
elif target == "info-only":
    relOutToRoot = "umakeGenerated.txt"
elif target == "cmake-script":
    relOutToRoot = "umakeGenerated.cmake"
elif target.startswith("cmake"):
    relOutToRoot = "umakeGenerated.txt"
else:
    relOutToRoot = "umakeGenerated.txt"
relOutToCur: str = path.join(root, relOutToRoot)

autoObj = not args.no_auto_obj
extHeaders: set[str] = set(args.ext_header)
extSources: set[str] = set(args.ext_source)
extHeaderSourcePairs: dict[str, str] = dict(args.ext_header_source)
