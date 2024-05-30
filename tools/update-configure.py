#!/usr/bin/env python3

usage = """This script downloads the single parameter which should be a
sqlite amalgamation including configure such as

https://sqlite.org/2024/sqlite-autoconf-3460000.tar.gz

and then updates the sqlite3/configure/ directory to ensure the
various scripts in there are up to date.
"""

import sys

if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
    sys.exit(usage)

import urllib.request
import subprocess
import tarfile

# get the version tracked files
files = set(subprocess.check_output(["git", "ls-files"], cwd="sqlite3/configure", encoding="utf8").split())
# we don't want to overwrite our dummy file configure insists is present
files.remove("sqlite3.c")

with tarfile.open(mode="r:gz", fileobj=urllib.request.urlopen(sys.argv[1])) as tarf:
    while True:
        member = tarf.next()
        if not member:
            break
        if "/" not in member.name:
            continue
        name = member.name.split("/", 1)[1]

        if name in files:
            with open(f"sqlite3/configure/{name}", "rb") as file:
                old_data = file.read()
            new_data = tarf.extractfile(member).read()
            if old_data != new_data:
                print(f"Updating {file.name}")
                with open(file.name, "wb") as file:
                    file.write(new_data)
