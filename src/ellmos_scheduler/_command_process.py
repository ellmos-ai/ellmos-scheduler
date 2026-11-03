"""Owned, noninteractive command lifetime and bounded output capture.

Windows binds a trusted unopened gate to a non-breakaway Job. A POSIX gate
signals its own session group when its owner's control pipe closes. This is not an
OS privilege sandbox; POSIX programs can deliberately escape their group.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time

OUTPUT_LIMIT = 16 * 1024 * 1024
_CLEANUP_SECONDS = 20.0
_GATE = r'''
import json,os,signal,subprocess,sys,threading,time
kind=sys.argv[1]
status_fd=None
if kind=='posix':
    status_fd=int(sys.argv[2])
    os.set_inheritable(status_fd,False)
    if os.getpgrp()!=os.getpid():
        raise SystemExit(86)
    signal.signal(signal.SIGPIPE,signal.SIG_IGN)
def exact(size):
    data=bytearray()
    while len(data)<size:
        part=os.read(0,size-len(data))
        if not part:
            raise SystemExit(86)
        data.extend(part)
    return bytes(data)
size=int.from_bytes(exact(4),'big')
if not 0<size<=1048576:
    raise SystemExit(86)
payload=json.loads(exact(size))
if type(payload) is not dict or set(payload)!={'argv','detach_on_success'}:
    raise SystemExit(86)
argv=payload['argv']
detach_on_success=payload['detach_on_success']
if type(detach_on_success) is not bool:
    raise SystemExit(86)
if type(argv) is not list or not argv or not all(type(v) is str for v in argv):
    raise SystemExit(86)
code=None
if kind=='posix':
    def owner_gone():
        try:
            message=os.read(0,1)
            if message==b'D' and detach_on_success and code==0:
                try:
                    os.write(status_fd,b'D\n')
                except OSError:
                    pass
                else:
                    os._exit(0)
        finally:
            try:
                os.write(status_fd,b'K\n')
            except OSError:
                pass
            os.killpg(os.getpgrp(),signal.SIGKILL)
    threading.Thread(target=owner_gone,daemon=True).start()
    os.write(status_fd,b'A\n')
try:
    options=dict(stdin=subprocess.DEVNULL,close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW if kind=='win' else 0)
    if detach_on_success:
        options.update(stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    code=subprocess.call(argv,**options)
except (OSError,ValueError) as error:
    print(str(error),file=sys.stderr,flush=True)
    code=127
if kind=='win':
    raise SystemExit(code)
try:
    os.write(status_fd,('R '+str(code)+'\n').encode('ascii'))
except OSError:
    os.killpg(os.getpgrp(),signal.SIGKILL)
sys.stdout.flush()
sys.stderr.flush()
os.close(1)
os.close(2)
# The owner closes its control pipe on completion/timeout. Only this gate
# signals its own group; the controller never targets a rediscovered POSIX PID.
while True:
    time.sleep(3600)
'''


def run_command(argv: list[str], *, cwd: str | None, env: dict[str, str], timeout: float,
                detach_on_success: bool = False):
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("command timeout must be finite and positive")
    if type(detach_on_success) is not bool:
        raise ValueError("background handoff must be an explicit boolean")
    encoded = json.dumps({'argv': argv, 'detach_on_success': detach_on_success}, ensure_ascii=True).encode('ascii')
    if len(encoded) > 1024 * 1024:
        raise ValueError("command argv exceeds gate byte bound")
    frame = len(encoded).to_bytes(4, 'big') + encoded
    deadline = time.monotonic() + timeout
    process = job = None
    assigned = False
    read_fd = write_fd = None
    threads: list[threading.Thread] = []
    status_thread = None
    output = [bytearray(), bytearray()]
    guard = threading.Lock()
    exceeded = threading.Event()
    capture_failed = threading.Event()
    status_done = threading.Event()
    admitted = threading.Event()
    group_stop_requested = threading.Event()
    detached = threading.Event()
    child_code: list[int | None] = [None]
    timed_out = False
    handoff = False

    def capture(stream, index):
        try:
            while chunk := stream.read(65536):
                with guard:
                    if sum(map(len, output)) + len(chunk) > OUTPUT_LIMIT:
                        exceeded.set()
                    elif not exceeded.is_set():
                        output[index].extend(chunk)
        except (OSError, ValueError):
            capture_failed.set()

    def send():
        try:
            view = memoryview(frame)
            while view:
                count = process.stdin.write(view[:4096])
                if not count:
                    raise OSError("command gate pipe did not accept input")
                view = view[count:]
        except (BrokenPipeError, OSError, ValueError):
            pass

    def receive_status(fd):
        try:
            data = bytearray()
            while chunk := os.read(fd, 1):
                data.extend(chunk)
                if len(data) >= 64:
                    raise ValueError("invalid command status")
                if chunk == b'\n':
                    line = bytes(data)
                    data.clear()
                    if line == b'A\n':
                        admitted.set()
                    elif line == b'K\n':
                        group_stop_requested.set()
                    elif line == b'D\n':
                        detached.set()
                    elif line.startswith(b'R '):
                        child_code[0] = int(line[2:].decode('ascii').strip())
                        status_done.set()
                    else:
                        raise ValueError("invalid command status")
            if data:
                raise ValueError("incomplete command status")
        except (ValueError, OSError, UnicodeError):
            capture_failed.set()
        finally:
            os.close(fd)
            if not status_done.is_set() and not group_stop_requested.is_set():
                capture_failed.set()

    def start(target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True)
        try:
            thread.start()
        except RuntimeError as error:
            raise OSError("command IO worker is unavailable") from error
        threads.append(thread)

    try:
        if os.name == 'nt':
            from ._windows_job import WindowsJob
            job = WindowsJob()
            job.__enter__()
            gate = [sys.executable, '-I', '-S', '-B', '-c', _GATE, 'win']
            options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            read_fd, write_fd = os.pipe()
            gate = [sys.executable, '-I', '-S', '-B', '-c', _GATE, 'posix', str(write_fd)]
            options = {'start_new_session': True, 'pass_fds': (write_fd,)}
        process = subprocess.Popen(gate, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, **options)
        if job is not None:
            try:
                job.assign(process)
            except (AttributeError, TypeError) as error:
                raise OSError("held command gate handle is unavailable") from error
            assigned = True
        else:
            os.close(write_fd)
            write_fd = None
            receiver = threading.Thread(target=receive_status, args=(read_fd,), daemon=True)
            try:
                receiver.start()
            except RuntimeError as error:
                raise OSError("command status worker is unavailable") from error
            status_thread = receiver
            read_fd = None  # The status thread now owns this descriptor.
        start(capture, process.stdout, 0)
        start(capture, process.stderr, 1)
        start(send)
        while True:
            if exceeded.is_set() or capture_failed.is_set():
                break
            # The POSIX gate reports its producer's exit while retaining its
            # own control pipe; only the gate signals its own process group.
            finished = process.poll() is not None if os.name == 'nt' else status_done.is_set()
            if finished and not any(thread.is_alive() for thread in threads):
                code = process.returncode if os.name == 'nt' else child_code[0]
                handoff = detach_on_success and code == 0
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.01)
    finally:
        cleanup_deadline = time.monotonic() + _CLEANUP_SECONDS
        cleanup_error = None
        try:
            if process is not None:
                if job is not None:
                    if assigned:
                        if handoff:
                            job.detach_after_success()
                        else:
                            job.terminate_and_wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
                    else:
                        process.kill()  # Only the held, unopened trusted gate.
                else:
                    if handoff and process.stdin.write(b'D') != 1:
                        raise OSError("background handoff release was not sent")
                    process.stdin.close()
        except (OSError, TimeoutError) as error:
            cleanup_error = error
        finally:
            # Closing a Windows Job kills descendants before any potentially
            # blocking pipe close, including when explicit termination fails.
            if job is not None:
                try:
                    job.__exit__(None, None, None)
                except OSError as error:
                    cleanup_error = error
            if process is not None:
                try:
                    process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
                except (OSError, subprocess.TimeoutExpired) as error:
                    cleanup_error = error
                for thread in threads:
                    thread.join(timeout=max(0.0, cleanup_deadline - time.monotonic()))
                if status_thread is not None:
                    status_thread.join(timeout=max(0.0, cleanup_deadline - time.monotonic()))
                    if status_thread.is_alive():
                        cleanup_error = OSError("command gate status termination is unconfirmed")
                    if handoff:
                        if not detached.is_set() or process.returncode != 0:
                            cleanup_error = OSError("background handoff is unconfirmed")
                    elif admitted.is_set() and (
                            not group_stop_requested.is_set() or process.returncode != -signal.SIGKILL):
                        cleanup_error = OSError("command gate group stop is unconfirmed")
                if any(thread.is_alive() for thread in threads):
                    cleanup_error = OSError("command output/input termination is unconfirmed")
                else:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream is not None:
                            with contextlib.suppress(BrokenPipeError):
                                stream.close()
            for fd in (read_fd, write_fd):
                if fd is not None:
                    os.close(fd)
        if cleanup_error is not None:
            raise OSError("command containment cleanup is unconfirmed") from cleanup_error
    stdout, stderr = map(bytes, output)
    if timed_out:
        raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr)
    if exceeded.is_set():
        raise ValueError("command output exceeds 16 MiB combined byte bound")
    if capture_failed.is_set() or (os.name != 'nt' and child_code[0] is None):
        raise OSError("command output/status capture failed")
    return subprocess.CompletedProcess(argv, process.returncode if os.name == 'nt' else child_code[0], stdout, stderr)
