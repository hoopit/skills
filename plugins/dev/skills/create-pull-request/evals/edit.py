"""`edit.py <file> <old> <new>`: replace the one occurrence of `old`, for a case's setup.sh.

Fails when `old` is not there exactly once, so a fixture whose code moved stops the run
instead of handing the agent a change that is not the one its prompt describes.
"""
import sys

path, old, new = sys.argv[1:4]
text = open(path).read()
if text.count(old) != 1:
    sys.exit(f"{path}: expected one {old!r}, found {text.count(old)}")
open(path, "w").write(text.replace(old, new))
