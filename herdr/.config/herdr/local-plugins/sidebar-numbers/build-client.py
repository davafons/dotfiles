#!/usr/bin/env python3
"""Build the sidebar plugin's Herdr 0.9.3 client companion."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request


VERSION = "0.9.3"
ARCHIVE_URL = f"https://codeload.github.com/herdrdev/herdr/tar.gz/refs/tags/v{VERSION}"
ARCHIVE_SHA256 = "e48f6706440c92362773663131ef5b524c62549523e50a03f2b55d315edca100"


def run(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True)


def prepare(source, patch):
    stamp = source / ".sidebar-numbers-patch"
    digest = hashlib.sha256(patch.read_bytes()).hexdigest()
    if stamp.exists():
        if stamp.read_text().strip() != digest:
            raise RuntimeError(f"Patch changed; use a fresh --source directory instead of {source}")
        return
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=source.parent, prefix="herdr-download-") as temporary:
            archive = Path(temporary) / "source.tar.gz"
            urllib.request.urlretrieve(ARCHIVE_URL, archive)
            if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
                raise RuntimeError("Herdr source checksum mismatch")
            with tarfile.open(archive) as bundle:
                bundle.extractall(temporary, filter="data")
            (Path(temporary) / f"herdr-{VERSION}").rename(source)
    manifest = (source / "Cargo.toml").read_text()
    if f'version = "{VERSION}"' not in manifest:
        raise RuntimeError(f"Expected Herdr {VERSION} sources in {source}")
    applied = subprocess.run(
        ["patch", "--dry-run", "--force", "-R", "-p1", "-i", str(patch)],
        cwd=source, capture_output=True,
    )
    if applied.returncode != 0:
        run("patch", "--dry-run", "--force", "-p1", "-i", str(patch), cwd=source)
        run("patch", "--force", "-p1", "-i", str(patch), cwd=source)
    stamp.write_text(digest + "\n")


def install(binary, destination):
    destination = destination.expanduser().absolute()
    if destination.is_symlink():
        raise RuntimeError(f"Refusing to replace symlink {destination}")
    if destination.exists():
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()[:12]
        backup = destination.with_name(destination.name + ".before-sidebar-" + digest)
        if not backup.exists():
            shutil.copy2(destination, backup)
        print(f"Previous binary: {backup}", flush=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".herdr-", delete=False) as temporary:
        staged = Path(temporary.name)
    try:
        shutil.copy2(binary, staged)
        staged.chmod(0o755)
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)
    print(f"Installed {destination}; detach and reattach clients to load it.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() / ".cache/herdr-sidebar-client" / VERSION)
    parser.add_argument("--install", type=Path, help="Atomically replace this binary after tests and build; retain a backup")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    patch = Path(__file__).resolve().with_name("client.patch")
    prepare(source, patch)
    run("cargo", "test", "--locked", "--bin", "herdr", "client::shell::", cwd=source)
    run("cargo", "build", "--locked", "--release", "--bin", "herdr", cwd=source)
    binary = source / "target/release/herdr"
    print(f"Built {binary}", flush=True)
    if args.install:
        install(binary, args.install)


if __name__ == "__main__":
    main()
