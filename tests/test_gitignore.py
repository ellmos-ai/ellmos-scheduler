"""Exercise Git's actual ignore semantics without user-global exclusion rules."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ignored_paths(tmp_path):
    git = shutil.which('git')
    if git is None:
        pytest.skip('Git is required to verify repository exclusion semantics')
    blank = tmp_path/'empty-config'
    blank.write_text('', encoding='utf-8')
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(blank), GIT_CONFIG_NOSYSTEM='1')
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    repository = tmp_path/'repo'
    repository.mkdir()
    (repository/'.gitignore').write_bytes((ROOT/'.gitignore').read_bytes())
    subprocess.run([git, '-c', 'init.templateDir=', 'init', '-q', str(repository)],
                   check=True, env=env, capture_output=True)

    def check(paths):
        result = subprocess.run(
            [git, '-c', f'core.excludesFile={blank}', 'check-ignore', '--no-index', '-z', '--stdin'],
            input='\0'.join(paths)+'\0', text=True, encoding='utf-8',
            cwd=repository, env=env, capture_output=True, check=False)
        assert result.returncode in (0, 1), result.stderr
        return set(filter(None, result.stdout.split('\0')))

    return check


@pytest.mark.parametrize('prefix', ['', 'local/session/'])
def test_local_sqlite_state_and_sidecars_are_private(ignored_paths, prefix):
    paths = [prefix+'scheduler'+suffix+sidecar
             for suffix in ('.db', '.sqlite', '.sqlite3')
             for sidecar in ('', '-wal', '-shm', '-journal')]
    assert ignored_paths(paths) == set(paths)


@pytest.mark.parametrize('prefix', ['', 'local/session/'])
def test_conventional_auth_artifacts_are_private(ignored_paths, prefix):
    paths = [prefix+name for name in (
        '.env', '.env.local', '.auth.json', '.credentials.json', 'credentials.json',
        '.secrets.json', 'secrets.json', 'token.json', 'tokens.json',
        '.auth/session.json', '.credentials/provider.json')]
    assert ignored_paths(paths) == set(paths)


@pytest.mark.parametrize('prefix', ['', 'examples/'])
def test_examples_and_source_remain_trackable(ignored_paths, prefix):
    paths = [prefix+name for name in (
        '.env.example', '.env.sample', '.env.template', 'credentials.json.example',
        'tokens.json.example', 'scheduler.sqlite.example', 'config.json',
        'test_store.py', 'README.md')]
    assert ignored_paths(paths) == set()
