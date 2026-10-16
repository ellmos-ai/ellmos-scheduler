from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ellmos_scheduler.executors import command_executor


def _payload(tmp_path, *, delay, parent_hold=0, inherit_pipes=False):
    marker, started, ready = (tmp_path/name for name in ('late-write', 'child-started', 'parent-ready'))
    child = (
        'import pathlib,time;'
        f'pathlib.Path({str(started)!r}).write_text(str(time.monotonic()));'
        f'time.sleep({delay});pathlib.Path({str(marker)!r}).write_text("late")'
    )
    streams = '' if inherit_pipes else ',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL'
    parent = (
        'import pathlib,subprocess,sys,time\n'
        f'subprocess.Popen([sys.executable,"-I","-S","-c",{child!r}],stdin=subprocess.DEVNULL{streams})\n'
        'deadline=time.monotonic()+5\n'
        f'while not pathlib.Path({str(started)!r}).is_file():\n'
        '    if time.monotonic()>deadline: raise SystemExit(2)\n'
        '    time.sleep(0.01)\n'
        f'pathlib.Path({str(ready)!r}).write_text("ready")\n'
        f'time.sleep({parent_hold})\n'
    )
    return {'argv': [sys.executable, '-I', '-S', '-c', parent]}, marker, started, ready


def _after_child_deadline(started, delay):
    target = float(started.read_text()) + delay + 0.5
    time.sleep(max(0, target - time.monotonic()))


def test_timeout_bounds_inherited_pipes_and_stops_owned_descendant(tmp_path):
    payload, marker, started, ready = _payload(tmp_path, delay=6, parent_hold=8, inherit_pipes=True)
    begin = time.monotonic()
    result = command_executor(payload, 2)
    elapsed = time.monotonic() - begin
    assert ready.is_file(), result
    assert result.status == 'timed_out'
    assert elapsed < 5, elapsed
    _after_child_deadline(started, 6)
    assert not marker.exists()


def test_success_stops_remaining_owned_child_with_closed_pipes(tmp_path):
    payload, marker, started, ready = _payload(tmp_path, delay=3)
    result = command_executor(payload, 10)
    assert ready.is_file()
    assert result.status == 'succeeded', result
    _after_child_deadline(started, 3)
    assert not marker.exists()


def test_controller_death_stops_owned_work(tmp_path):
    payload, marker, started, ready = _payload(tmp_path, delay=3, parent_hold=6, inherit_pipes=True)
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    code = 'from ellmos_scheduler.executors import command_executor; command_executor(' + repr(payload) + ',20)'
    process = subprocess.Popen([sys.executable, '-B', '-c', code], env=env,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while not ready.is_file() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.01)
        assert ready.is_file(), process.poll()
        process.kill()  # This test owns the still-live controller Popen.
        process.wait(timeout=5)
        _after_child_deadline(started, 3)
        assert not marker.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_output_flood_fails_at_combined_byte_bound():
    code = 'import os\nfor _ in range(136):\n os.write(1,b"x"*65536)\n os.write(2,b"y"*65536)'
    result = command_executor({'argv': [sys.executable, '-I', '-S', '-c', code]}, 10)
    assert result.status == 'failed'
    assert '16 MiB' in result.error
    assert len(result.output) <= 16 * 1024 * 1024


def test_argument_environment_directory_exit_and_stdin_contract(tmp_path):
    arguments = ['Ü # % & | " literal', 'line\nbreak', '🐙']
    code = ('import json,os,sys;print(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd(),'
            '"env":os.environ["SCHEDULER_TEST_VALUE"],"stdin":sys.stdin.read()}));sys.exit(7)')
    result = command_executor({'argv': [sys.executable, '-I', '-S', '-c', code, *arguments],
                               'cwd': str(tmp_path), 'env': {'SCHEDULER_TEST_VALUE': 'retained'}}, 10)
    assert result.status == 'failed' and result.exit_code == 7
    value = json.loads(result.output)
    assert value['args'] == arguments
    assert Path(value['cwd']) == tmp_path
    assert value['env'] == 'retained' and value['stdin'] == ''


def test_cleanup_preserves_unrelated_synthetic_sibling(tmp_path):
    marker = tmp_path/'sibling-survived'
    code = f'import pathlib,time;time.sleep(1);pathlib.Path({str(marker)!r}).write_text("alive")'
    sibling = subprocess.Popen([sys.executable, '-I', '-S', '-c', code],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        result = command_executor({'argv': [sys.executable, '-I', '-S', '-c', 'pass']}, 10)
        assert result.status == 'succeeded'
        sibling.wait(timeout=5)
        assert marker.read_text() == 'alive'
    finally:
        if sibling.poll() is None:
            sibling.kill()
            sibling.wait(timeout=5)


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job containment failure injection')
@pytest.mark.parametrize('stage', ['__enter__', 'assign', 'terminate_and_wait'])
def test_windows_containment_failure_never_reports_success_or_leaves_work(tmp_path, monkeypatch, stage):
    from ellmos_scheduler._windows_job import WindowsJob

    payload, marker, started, ready = _payload(tmp_path, delay=3)

    def fail(*args, **kwargs):
        raise OSError('synthetic containment failure')

    monkeypatch.setattr(WindowsJob, stage, fail)
    result = command_executor(payload, 10)
    assert result.status == 'failed'
    if stage == 'terminate_and_wait':
        assert ready.is_file()
        _after_child_deadline(started, 3)
    else:
        assert not ready.exists()
    assert not marker.exists()


def _synthetic_marble_run(tmp_path, *, background, exit_code):
    # A local fake CLI exercises the real adapter without starting llmauto or a model.
    payload, marker, started, ready = _payload(tmp_path, delay=2)
    parent = payload['argv'][-1] + f'raise SystemExit({exit_code})\n'
    (tmp_path/'llmauto.py').write_text(parent, encoding='utf-8')
    return {'chain': 'fixture', 'background': background, 'cwd': str(tmp_path),
            'env': {'PYTHONPATH': str(tmp_path)}}, marker, started, ready


@pytest.mark.parametrize('background,exit_code,survives', [
    (True, 0, True), (False, 0, False), (True, 7, False),
])
def test_marble_run_handoff_only_after_explicit_success(tmp_path, background, exit_code, survives):
    from ellmos_scheduler.adapters import marblerun_executor

    payload, marker, started, ready = _synthetic_marble_run(
        tmp_path, background=background, exit_code=exit_code)
    result = marblerun_executor(payload, 10)
    assert ready.is_file(), result
    assert result.exit_code == exit_code, result
    assert result.status == ('succeeded' if exit_code == 0 else 'failed'), result
    if survives:
        assert 'dispatch' in result.output and 'chain completion' in result.output
    _after_child_deadline(started, 2)
    assert marker.exists() is survives


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job handoff failure injection')
def test_windows_failed_handoff_keeps_owned_child_contained(tmp_path, monkeypatch):
    from ellmos_scheduler._windows_job import WindowsJob
    from ellmos_scheduler.adapters import marblerun_executor

    payload, marker, started, ready = _synthetic_marble_run(tmp_path, background=True, exit_code=0)

    def fail(*args, **kwargs):
        raise OSError('synthetic background release failure')

    monkeypatch.setattr(WindowsJob, 'detach_after_success', fail)
    result = marblerun_executor(payload, 10)
    assert ready.is_file(), result
    assert result.status == 'failed', result
    _after_child_deadline(started, 2)
    assert not marker.exists()
