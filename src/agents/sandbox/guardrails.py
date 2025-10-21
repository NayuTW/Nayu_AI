import builtins
import io
import inspect
import os
import sys
from contextlib import ContextDecorator
from typing import Optional, Sequence

try:
    import resource  # POSIX only
except Exception:
    resource = None  # type: ignore

class StdoutLimiter(io.TextIOBase):
    def __init__(self, base: io.TextIOBase, max_lines: int = 200, max_bytes: int = 200_000):
        self.base = base
        self.max_lines = max_lines
        self.max_bytes = max_bytes
        self._lines = 0
        self._bytes = 0

    def write(self, s: str):
        if self._lines >= self.max_lines or self._bytes >= self.max_bytes:
            return 0
        lines_in_s = s.count("\n")
        new_lines = self._lines + lines_in_s
        if new_lines > self.max_lines:
            remaining = self.max_lines - self._lines
            parts = s.split("\n")
            s = "\n".join(parts[: remaining + 1])
            lines_in_s = remaining
        enc = s.encode("utf-8", "ignore")
        if self._bytes + len(enc) > self.max_bytes:
            remaining_b = self.max_bytes - self._bytes
            s = enc[:remaining_b].decode("utf-8", "ignore")
            enc = s.encode("utf-8", "ignore")
        self._lines += lines_in_s
        self._bytes += len(enc)
        return self.base.write(s)

    def flush(self):
        return self.base.flush()

class GuardedEnv(ContextDecorator):
    """
    Lightweight guardrails for the CodeAgent child process.
    Not a perfect sandbox; use as defense-in-depth with process isolation.
    """
    def __init__(
        self,
        *,
        allowed_imports: Optional[Sequence[str]] = None,
        allow_open_readonly: bool = False,
        open_read_roots: Optional[Sequence[str]] = None,
        disable_subprocess: bool = True,
        network_allowed_callers: Optional[Sequence[str]] = None,
        step_limit: int = 4000,
        print_line_limit: int = 200,
        print_byte_limit: int = 200_000,
        cpu_time_s: Optional[int] = None,
        mem_limit_mb: Optional[int] = None,
    ):
        self.allowed_imports = set(allowed_imports or [])
        self.allow_open_readonly = allow_open_readonly
        self.open_read_roots = [os.path.abspath(p) for p in (open_read_roots or ["./workspace"])]
        self.disable_subprocess = disable_subprocess
        self.network_allowed_callers = list(network_allowed_callers or [])
        self.step_limit = step_limit
        self.print_line_limit = print_line_limit
        self.print_byte_limit = print_byte_limit
        self.cpu_time_s = cpu_time_s
        self.mem_limit_mb = mem_limit_mb

        self._orig_import = builtins.__import__
        self._orig_open = builtins.open
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        self._orig_trace = sys.gettrace()
        self._orig_subprocess = {}
        self._orig_os = {}
        self._orig_shutil = {}
        self._orig_requests_request = None
        self._ops = 0

    def _guard_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        top_name = name.split(".", 1)[0]
        if top_name not in self.allowed_imports:
            raise ImportError(f"Import of module '{top_name}' is not allowed")
        return self._orig_import(name, globals, locals, fromlist, level)

    def _guard_open(self, file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise PermissionError("File write operations are not allowed")
        if not self.allow_open_readonly:
            raise PermissionError("File IO is disabled")
        path = os.path.abspath(file)
        if not any(path.startswith(root + os.sep) or path == root for root in self.open_read_roots):
            raise PermissionError(f"Read access outside allowed roots is not permitted: {path}")
        return self._orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    def _guarded_trace(self, frame, event, arg):
        if event in ("line", "call"):
            self._ops += 1
            if self._ops > self.step_limit:
                raise RuntimeError(f"Step limit exceeded ({self.step_limit})")
        return self._guarded_trace

    def _patch_subprocess(self):
        if not self.disable_subprocess:
            return
        import subprocess
        blocked = ("Popen", "call", "check_call", "check_output", "run")
        for name in blocked:
            if hasattr(subprocess, name):
                self._orig_subprocess[name] = getattr(subprocess, name)
                setattr(subprocess, name, self._raise_perm)
        self._orig_os["system"] = getattr(os, "system", None)
        setattr(os, "system", self._raise_perm)

    def _patch_filesystem_mutation(self):
        for mod, names in [
            (os, ["remove", "unlink", "rmdir", "removedirs", "rename", "replace"]),
        ]:
            for n in names:
                if hasattr(mod, n):
                    self._orig_os[n] = getattr(mod, n)
                    setattr(mod, n, self._raise_perm)
        try:
            import shutil  # type: ignore
            for n in ["move", "rmtree", "copy", "copy2", "copytree"]:
                if hasattr(shutil, n):
                    self._orig_shutil[n] = getattr(shutil, n)
                    setattr(shutil, n, self._raise_perm)
        except Exception:
            pass

    def _patch_requests_gateway(self):
        if not self.network_allowed_callers:
            return
        try:
            import requests  # type: ignore
            sess_cls = requests.sessions.Session
            if self._orig_requests_request is None:
                self._orig_requests_request = sess_cls.request
            allowed_prefixes = tuple(self.network_allowed_callers)
            def guarded_request(this, method, url, **kwargs):
                stack = inspect.stack()
                allowed = False
                for fr in stack:
                    mod = fr.frame.f_globals.get("__name__", "")
                    if mod.startswith(allowed_prefixes):
                        allowed = True
                        break
                if not allowed:
                    raise PermissionError("Network calls are only allowed from approved tool modules")
                return self._orig_requests_request(this, method, url, **kwargs)
            sess_cls.request = guarded_request  # type: ignore
        except Exception:
            pass

    def _raise_perm(self, *a, **kw):
        raise PermissionError("Operation not permitted by guardrails")

    def _apply_resource_limits(self):
        if resource is None:
            return
        try:
            if self.cpu_time_s is not None:
                resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_time_s, self.cpu_time_s))
            if self.mem_limit_mb is not None:
                bytes_ = int(self.mem_limit_mb * 1024 * 1024)
                for lim in (resource.RLIMIT_AS, resource.RLIMIT_DATA):
                    try:
                        resource.setrlimit(lim, (bytes_, bytes_))
                    except Exception:
                        pass
        except Exception:
            pass

    def __enter__(self):
        builtins.__import__ = self._guard_import  # type: ignore
        builtins.open = self._guard_open  # type: ignore
        for name in ("exec", "eval", "__import__"):
            if hasattr(builtins, name):
                setattr(builtins, name, self._raise_perm)
        sys.stdout = StdoutLimiter(self._orig_stdout, self.print_line_limit, self.print_byte_limit)
        sys.stderr = StdoutLimiter(self._orig_stderr, self.print_line_limit // 2, self.print_byte_limit // 2)
        sys.settrace(self._guarded_trace)
        self._patch_subprocess()
        self._patch_filesystem_mutation()
        self._patch_requests_gateway()
        self._apply_resource_limits()
        return self

    def __exit__(self, exc_type, exc, tb):
        builtins.__import__ = self._orig_import  # type: ignore
        builtins.open = self._orig_open  # type: ignore
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        sys.settrace(self._orig_trace)
        try:
            import subprocess
            for k, v in self._orig_subprocess.items():
                setattr(subprocess, k, v)
        except Exception:
            pass
        for k, v in self._orig_os.items():
            if v is None:
                try:
                    delattr(os, k)
                except Exception:
                    pass
            else:
                setattr(os, k, v)
        try:
            import shutil  # type: ignore
            for k, v in self._orig_shutil.items():
                setattr(shutil, k, v)
        except Exception:
            pass
        try:
            if self._orig_requests_request is not None:
                import requests  # type: ignore
                requests.sessions.Session.request = self._orig_requests_request  # type: ignore
        except Exception:
            pass
        return False