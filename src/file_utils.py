"""
This utils file contains helpers for accessing filepaths.
"""

from datetime import datetime
from typing import Dict, Callable, Any
from inspect import signature
from pathlib import Path
import sys

from .params import TMP_DIR


def pathlike(*arg_names: str):
    """
    Converts the arguments provided to Path objects before
    passing to the function.

    Parameters
    ----------
    *arg_names: str
        The different argument names that should be turned into Path
        objects.
    """

    def decorator(func: Callable[..., Any]):
        function_sig = signature(func)
        assert all(arg_name in function_sig.parameters for arg_name in arg_names)
        func.pathlike_arguments = arg_names  # type: ignore[attr-defined]

        def decorated_func(*args, **kwargs):
            bound_sig = function_sig.bind(*args, **kwargs)

            for arg_name in arg_names:
                to_path = bound_sig.arguments[arg_name]
                bound_sig.arguments[arg_name] = Path(to_path)
            res = func(**bound_sig.arguments)

            return res

        return decorated_func

    return decorator


# File utils
@pathlike("dirpath")
def safe_open_dir(dirpath: Path) -> Path:
    if not dirpath.is_dir():
        print(f"Directory {dirpath} does not exist, creating it")
        dirpath.mkdir(parents=True)
    return dirpath


@pathlike("fp")
def safe_open_file(fp: Path) -> Path:
    _ = safe_open_dir(fp.parent)
    return fp


@pathlike("fp")
def tag_file(fp: Path, **tags: str) -> Path:
    tag_strs = ["_".join(item) for item in tags.items()]
    new_canonical_filename = "_".join([fp.stem] + tag_strs)

    return fp.parent / (new_canonical_filename + fp.suffix)


### These two methods are useful for manipulating files that may need to
# be in a tmp directory
@pathlike("fp")
def tmp_path(fp: Path, debug=True) -> Path:
    return (safe_open_dir(TMP_DIR) / fp.name) if debug else safe_open_file(fp)


def tmp_paths(path_dict: Dict[str, str | Path], debug=True) -> Dict[str, Path]:
    return {k: tmp_path(fp, debug=debug) for k, fp in path_dict.items()}


class Tee(object):
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stdout = sys.stdout

    def close(self):
        self.file.close()

    def __del__(self):
        self.close()

    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)
        self.flush()

    def flush(self):
        self.file.flush()
        self.stdout.flush()
