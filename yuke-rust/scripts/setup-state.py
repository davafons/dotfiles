#!/usr/bin/env python3
"""Create the yuke-rust state that Stow does not link. Existing state stays unchanged.

Stow links the settings in .config/yuke-rust. This step adds what yuke-rust and its plugins
own at runtime:

- auth.json in the data folder, empty and mode 0600, for `yuke login` and stored API keys
- the model aliases seed, which the models plugin edits afterwards
- tsconfig.json in the profile, which names the installed SDK by absolute path

The task and inbox databases need no step: their stores create the tables on first use.
monid.key is a secret that the user copies into the profile; this step reports when it is missing.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def xdg(variable, home, fallback):
    value = Path(os.environ.get(variable, ''))
    return value if value.is_absolute() else home / fallback


def private_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        os.fchmod(temporary.fileno(), 0o600)
        temporary.write(data)
        temporary.flush()
        os.fsync(temporary.fileno())
        pending = temporary.name
    os.replace(pending, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--appname', default='yuke-rust')
    args = parser.parse_args()
    home = args.home
    profile = xdg('XDG_CONFIG_HOME', home, '.config') / args.appname
    data = xdg('XDG_DATA_HOME', home, '.local/share') / args.appname
    created = []

    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    auth = data / 'auth.json'
    if not auth.exists():
        private_write(auth, b'{}\n')
        created.append(str(auth))

    aliases = data / 'plugins/models/model-aliases.json'
    if not aliases.exists():
        private_write(aliases, (ROOT / 'state/model-aliases.json').read_bytes())
        created.append(str(aliases))

    tsconfig = profile / 'tsconfig.json'
    text = json.dumps({
        'extends': str(home / '.local/lib/yuke-rust/tsconfig.json'),
        'include': ['**/*.ts', '**/*.js'],
        'compilerOptions': {'allowJs': True, 'checkJs': True},
    }, indent=2) + '\n'
    if tsconfig.is_symlink() or not tsconfig.exists() or tsconfig.read_text() != text:
        if tsconfig.is_symlink():
            tsconfig.unlink()
        profile.mkdir(parents=True, exist_ok=True)
        tsconfig.write_text(text)
        created.append(str(tsconfig))

    missing = [str(path) for path in [profile / 'monid.key'] if not path.exists()]
    print(json.dumps({'created': created, 'missing_secrets': missing}, indent=2))


if __name__ == '__main__':
    main()
