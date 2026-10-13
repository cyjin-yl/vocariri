#!/usr/bin/env python3
"""Read selected published effect routines from an npm tarball without executing them."""
import argparse
import io
import re
import tarfile
from pathlib import Path


def close_brace(source: str, start: int) -> int:
    depth = 0
    quote = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced source method")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tarball", type=Path)
    parser.add_argument("names", nargs="+")
    args = parser.parse_args()
    with tarfile.open(fileobj=io.BytesIO(args.tarball.read_bytes()), mode="r:gz") as archive:
        source = archive.extractfile("package/dist/index.mjs").read().decode("utf-8")
        declarations = archive.extractfile("package/dist/index.d.ts").read().decode("utf-8")
    declared = re.search(r"type TypoEffect = (.*?);", declarations).group(1)
    names = re.findall(r"['\"]?([\w-]+)['\"]?", declared)
    implemented = [name for name in names if re.search(
        rf"(?:['\"]{re.escape(name)}['\"]|{re.escape(name)})\(a,e,s,i,n\)\{{", source
    )]
    print(f"declared={len(names)} method_signatures={len(implemented)}")
    for name in args.names:
        match = re.search(
            rf"(?:['\"]{re.escape(name)}['\"]|{re.escape(name)})\(a,e,s,i,n\)\{{", source
        )
        index = match.start() if match else -1
        if index < 0:
            print(f"--- {name}: not found ---")
            continue
        opening = source.find("{", index)
        ending = close_brace(source, opening)
        print(f"--- {name} ---\n{source[index:ending + 1]}")


if __name__ == "__main__":
    main()
