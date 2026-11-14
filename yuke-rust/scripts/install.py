#!/usr/bin/env python3
"""Install a verified native yuke-rust package. Activate it as the default `yuke` only with --activate."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def atomic(path, text, mode=0o755):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(text.encode())
        os.fchmod(temporary.fileno(), mode)
        temporary.flush()
        os.fsync(temporary.fileno())
        pending = temporary.name
    os.replace(pending, path)

def link(path, target):
    pending = path.with_name(path.name + '.migration-pending')
    if pending.is_symlink():
        pending.unlink()
    pending.symlink_to(target, target_is_directory=True)
    os.replace(pending, path)

def wrapper(binary, app):
    # Paths use shell single-quote escaping, not JSON escaping.
    quoted = "'" + str(binary).replace("'", "'\"'\"'") + "'"
    return '#!/bin/sh\nexport YUKE_APPNAME="${YUKE_APPNAME:-' + app + '}"\nexport YUKE_EXECUTABLE=' + quoted + '\nexec ' + quoted + ' "$@"\n'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path.home() / 'workspace/yuke')
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    archive = args.archive.resolve(strict=True)
    home = Path.home()
    local = home / '.local'
    spec = importlib.util.spec_from_file_location('package', source / 'tools/package.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    source_hash = package.source_state()
    release = local / 'lib/yuke-rust-releases' / source_hash[:16]
    release.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.rust-install-', dir=release.parent) as directory:
        import tarfile
        staging = Path(directory)
        with tarfile.open(archive) as contents:
            contents.extractall(staging, filter='data')
        sdk = staging / 'lib/yuke'
        (sdk / 'bin').mkdir()
        shutil.copy2(staging / 'bin/yuke', sdk / 'bin/yuke')
        identity = json.loads((sdk / 'build.json').read_text())
        identity['sourceHash'] = source_hash
        identity['source'] = str(source)
        identity['archiveSha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        (sdk / 'build.json').write_text(json.dumps(identity, indent=2) + '\n')
        shutil.copytree(source / 'docs', sdk / 'docs')
        shutil.copytree(ROOT / 'skills', sdk / 'skills')
        version = subprocess.check_output([str(sdk / 'bin/yuke'), '--version'], text=True).strip()
        if version != 'yuke ' + identity['version']:
            raise RuntimeError('The executable and package identity differ.')
        # Every installation receives a complete directory before the public link moves.
        if release.exists():
            existing = json.loads((release / 'build.json').read_text())
            if existing['archiveSha256'] != identity['archiveSha256']:
                raise RuntimeError('A different package already uses this source identity.')
        else:
            shutil.move(sdk, release)
    public = local / 'lib/yuke-rust'
    # Verify the candidate before a running default command can resolve its public link.
    subprocess.run(['python3', str(ROOT / 'scripts/verify.py'), '--source', str(source), '--binary', str(release / 'bin/yuke')], check=True)
    link(public, release)
    bin_dir = local / 'bin'
    current = bin_dir / 'yuke'
    atomic(bin_dir / 'yuke-rust', wrapper(public / 'bin/yuke', 'yuke-rust'))
    if args.activate:
        atomic(current, wrapper(public / 'bin/yuke', 'yuke-rust'))
        link(home / '.agents/skills/yuke', public / 'skills/yuke')
    print(json.dumps(dict(version=identity['version'], sourceHash=source_hash, release=str(release), default='rust' if args.activate else 'unchanged'), indent=2))

if __name__ == '__main__':
    main()
