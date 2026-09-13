"""C bindings + config/help loading for AllTool.

Compatibility contract (installer.sh + Makefile, DO NOT BREAK):
  - C libs live in ~/.config/alltool/bin (LIB_DIR), built via Tools/c_src/Makefile
    (`make install-user`, `make install-c`, `make dev-install`).
  - Config: ~/.config/alltool/.confs.json (fallback: repo .confs.json, then defaults).
  - Help:   ~/.config/alltool/.help.json (fallback: repo .help.json, then minimal).
  - `alltool_runner` binary lives next to the .so files.

Optimization vs old version:
  - Lazy per-library loading: importing this module or constructing ToolBase
    never crashes when .so files are missing (dev/CI without `make build-c`).
  - Pure-Python fallbacks: compiler (gcc/g++) and sudo work without C libs.
  - Cached config/help reads (one disk read per process).
"""
import ctypes
import json
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

HOME_DIR = Path.home() / ".config" / "alltool"
BIN_DIR = HOME_DIR / "bin"
LIB_DIR = BIN_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent

_shm_lib = None
_compiler_lib = None
_sudo_lib = None
_libs_probed: Dict[str, bool] = {}

_config_cache: Optional[Dict[str, Any]] = None
_help_cache: Dict[str, Dict[str, Any]] = {}


# C structure definitions at module level
class CompileOpts(ctypes.Structure):
    _fields_ = [
        ("source_path", ctypes.c_char_p),
        ("output_path", ctypes.c_char_p),
        ("cache_dir", ctypes.c_char_p),
        ("temp_mode", ctypes.c_bool),
        ("compiler_flags", ctypes.c_char_p),
        ("lang", ctypes.c_int),
    ]


class CompileResult(ctypes.Structure):
    _fields_ = [
        ("exit_code", ctypes.c_int),
        ("output_path", ctypes.c_char_p),
        ("error_message", ctypes.c_char_p),
        ("exec_output", ctypes.c_char_p),
        ("compile_time_ms", ctypes.c_double),
        ("exec_time_ms", ctypes.c_double),
    ]


class SudoCreds(ctypes.Structure):
    _fields_ = [
        ("username", ctypes.c_char_p),
        ("encrypted_password", ctypes.c_char_p),
        ("salt", ctypes.c_char_p),
        ("cached", ctypes.c_bool),
    ]


def _lib_path(name: str) -> Path:
    ext = ".so" if platform.system() == "Linux" else ".dylib"
    return LIB_DIR / f"{name}{ext}"


def _try_load(name: str):
    """Load one .so lazily. Returns None (never raises) when missing."""
    global _shm_lib, _compiler_lib, _sudo_lib
    key = name
    existing = {"liballtool_shm": _shm_lib,
                "liballtool_compiler": _compiler_lib,
                "liballtool_sudo": _sudo_lib}[name]
    if existing is not None or _libs_probed.get(key):
        return existing
    _libs_probed[key] = True
    try:
        lib = ctypes.CDLL(str(_lib_path(name)))
    except OSError:
        return None
    try:
        if name == "liballtool_shm":
            _setup_shm_bindings(lib)
            _shm_lib = lib
        elif name == "liballtool_compiler":
            _setup_compiler_bindings(lib)
            _compiler_lib = lib
        elif name == "liballtool_sudo":
            _setup_sudo_bindings(lib)
            _sudo_lib = lib
    except (AttributeError, OSError):
        return None
    return {"liballtool_shm": _shm_lib,
            "liballtool_compiler": _compiler_lib,
            "liballtool_sudo": _sudo_lib}[name]


def _setup_shm_bindings(lib):
    lib.alltool_shm_init.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    lib.alltool_shm_init.restype = ctypes.c_int
    lib.alltool_shm_attach.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    lib.alltool_shm_attach.restype = ctypes.c_int
    lib.alltool_shm_register_process.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int32]
    lib.alltool_shm_register_process.restype = ctypes.c_int
    lib.alltool_shm_wait_predecessor.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.alltool_shm_wait_predecessor.restype = ctypes.c_int
    lib.alltool_shm_send_payload.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    lib.alltool_shm_send_payload.restype = ctypes.c_int
    lib.alltool_shm_recv_payload.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    lib.alltool_shm_recv_payload.restype = ctypes.c_int
    lib.alltool_shm_mark_done.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.alltool_shm_mark_done.restype = ctypes.c_int
    lib.alltool_shm_detach.argtypes = [ctypes.c_void_p]
    lib.alltool_shm_detach.restype = None
    lib.alltool_shm_cleanup.argtypes = [ctypes.c_char_p]
    lib.alltool_shm_cleanup.restype = None


def _setup_compiler_bindings(lib):
    lib.alltool_detect_language.argtypes = [ctypes.c_char_p]
    lib.alltool_detect_language.restype = ctypes.c_int
    lib.alltool_lang_to_string.argtypes = [ctypes.c_int]
    lib.alltool_lang_to_string.restype = ctypes.c_char_p
    lib.alltool_get_compiler.argtypes = [ctypes.c_int]
    lib.alltool_get_compiler.restype = ctypes.c_char_p
    lib.alltool_compile_and_run.argtypes = [ctypes.POINTER(CompileOpts), ctypes.POINTER(CompileResult)]
    lib.alltool_compile_and_run.restype = ctypes.c_int
    lib.alltool_free_result.argtypes = [ctypes.POINTER(CompileResult)]
    lib.alltool_free_result.restype = None
    lib.alltool_get_cache_path.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.alltool_get_cache_path.restype = ctypes.c_char_p


def _setup_sudo_bindings(lib):
    lib.alltool_sudo_prompt_credentials.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_char_p)]
    lib.alltool_sudo_prompt_credentials.restype = ctypes.c_int
    lib.alltool_sudo_encrypt_password.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    lib.alltool_sudo_encrypt_password.restype = ctypes.c_int
    lib.alltool_sudo_verify_password.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    lib.alltool_sudo_verify_password.restype = ctypes.c_int
    lib.alltool_sudo_generate_salt.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
    lib.alltool_sudo_generate_salt.restype = ctypes.c_int
    lib.alltool_sudo_run_with_creds.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    lib.alltool_sudo_run_with_creds.restype = ctypes.c_int
    lib.alltool_sudo_cache_credentials.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    lib.alltool_sudo_cache_credentials.restype = ctypes.c_int
    lib.alltool_sudo_load_credentials.argtypes = [ctypes.c_char_p, ctypes.POINTER(SudoCreds)]
    lib.alltool_sudo_load_credentials.restype = ctypes.c_int
    lib.alltool_sudo_free_creds.argtypes = [ctypes.POINTER(SudoCreds)]
    lib.alltool_sudo_free_creds.restype = None
    lib.alltool_sudo_clear_cache.argtypes = [ctypes.c_char_p]
    lib.alltool_sudo_clear_cache.restype = ctypes.c_int


@dataclass
class CompileResultPy:
    exit_code: int
    output_path: Optional[str]
    error_message: Optional[str]
    exec_output: Optional[str]
    compile_time_ms: float
    exec_time_ms: float


class AllToolSHM:
    def __init__(self, name: str = "/alltool_chain", size: int = 65536):
        lib = _try_load("liballtool_shm")
        if lib is None:
            raise RuntimeError(
                f"SHM C library not found at {_lib_path('liballtool_shm')}. "
                "Run `make install-user` / `make build-c` to build it."
            )
        self._lib = lib
        self.name = name.encode()
        self.size = size
        self.ctx = ctypes.create_string_buffer(ctypes.sizeof(ctypes.c_void_p) * 4)
        self._init()

    def _init(self):
        ret = self._lib.alltool_shm_init(self.name, self.size)
        if ret != 0:
            raise RuntimeError(f"Failed to initialize SHM: {ret}")
        ret = self._lib.alltool_shm_attach(self.name, self.ctx)
        if ret != 0:
            raise RuntimeError(f"Failed to attach to SHM: {ret}")

    def register_process(self, pid: int, predecessor_idx: int) -> int:
        return self._lib.alltool_shm_register_process(self.ctx, pid, predecessor_idx)

    def wait_predecessor(self, timeout_ms: int = -1) -> int:
        return self._lib.alltool_shm_wait_predecessor(self.ctx, timeout_ms)

    def send_payload(self, data: bytes) -> int:
        return self._lib.alltool_shm_send_payload(self.ctx, data, len(data))

    def recv_payload(self, buffer_size: int = 4096) -> bytes:
        buffer = ctypes.create_string_buffer(buffer_size)
        size = ctypes.c_size_t(buffer_size)
        ret = self._lib.alltool_shm_recv_payload(self.ctx, buffer, ctypes.byref(size))
        if ret != 0:
            return b""
        return buffer.raw[:size.value]

    def mark_done(self, status: int) -> int:
        return self._lib.alltool_shm_mark_done(self.ctx, status)

    def detach(self):
        self._lib.alltool_shm_detach(self.ctx)

    def cleanup(self):
        self._lib.alltool_shm_cleanup(self.name)


_C_EXTS = {".c": "gcc", ".cc": "g++", ".cpp": "g++", ".cxx": "g++"}


class AllToolCompiler:
    """Uses liballtool_compiler.so when present, else pure-Python gcc/g++."""

    def __init__(self):
        self._lib = _try_load("liballtool_compiler")

    def detect_language(self, filename: str) -> int:
        if self._lib is not None:
            return self._lib.alltool_detect_language(filename.encode())
        return 0

    def lang_to_string(self, lang: int) -> str:
        if self._lib is not None:
            v = self._lib.alltool_lang_to_string(lang)
            return v.decode() if v else "unknown"
        return "unknown"

    def get_compiler(self, lang: int) -> str:
        if self._lib is not None:
            v = self._lib.alltool_get_compiler(lang)
            return v.decode() if v else "cc"
        return "cc"

    def compile_and_run(self, source_path: str, cache_dir: str = None,
                        temp_mode: bool = False,
                        compiler_flags: str = "-O2 -pipe",
                        output_path: str = None) -> CompileResultPy:
        if self._lib is not None:
            return self._compile_and_run_c(source_path, cache_dir, temp_mode,
                                           compiler_flags, output_path)
        return self._compile_and_run_py(source_path, cache_dir, temp_mode,
                                        compiler_flags, output_path)

    def _compile_and_run_c(self, source_path, cache_dir, temp_mode,
                           compiler_flags, output_path) -> CompileResultPy:
        opts = CompileOpts()
        opts.source_path = source_path.encode()
        opts.output_path = output_path.encode() if output_path else None
        opts.cache_dir = cache_dir.encode() if cache_dir else str(HOME_DIR / "cache").encode()
        opts.temp_mode = temp_mode
        opts.compiler_flags = compiler_flags.encode()
        opts.lang = self.detect_language(source_path)
        result = CompileResult()
        self._lib.alltool_compile_and_run(ctypes.byref(opts), ctypes.byref(result))
        out = CompileResultPy(
            exit_code=result.exit_code,
            output_path=result.output_path.decode() if result.output_path else None,
            error_message=result.error_message.decode() if result.error_message else None,
            exec_output=result.exec_output.decode() if result.exec_output else None,
            compile_time_ms=result.compile_time_ms,
            exec_time_ms=result.exec_time_ms,
        )
        self._lib.alltool_free_result(ctypes.byref(result))
        return out

    def _compile_and_run_py(self, source_path, cache_dir, temp_mode,
                            compiler_flags, output_path) -> CompileResultPy:
        """Fallback when the C lib is not built. Handles C/C++ only."""
        import hashlib
        import os
        ext = os.path.splitext(source_path)[1].lower()
        cc = _C_EXTS.get(ext)
        if cc is None:
            return CompileResultPy(1, None,
                                   f"❌ No compiler available for '{ext}' (C lib missing, fallback covers .c/.cc/.cpp/.cxx only).",
                                   None, 0.0, 0.0)
        if shutil.which(cc) is None:
            return CompileResultPy(1, None, f"❌ Compiler '{cc}' not found.", None, 0.0, 0.0)
        if output_path:
            exe = output_path
        elif temp_mode:
            exe = f"/tmp/alltool_{os.getpid()}"
        else:
            h = hashlib.sha256(f"{source_path}:{compiler_flags}".encode()).hexdigest()[:16]
            base = cache_dir or str(HOME_DIR / "cache")
            os.makedirs(base, exist_ok=True)
            exe = os.path.join(base, f"alltool_{h}")
        t0 = time.perf_counter()
        comp = subprocess.run([cc, source_path, "-o", exe] + compiler_flags.split(),
                              capture_output=True, text=True)
        compile_ms = (time.perf_counter() - t0) * 1000.0
        if comp.returncode != 0:
            return CompileResultPy(comp.returncode, None, comp.stderr.strip() or "compilation failed",
                                   None, compile_ms, 0.0)
        t1 = time.perf_counter()
        run = subprocess.run([exe], capture_output=True, text=True)
        exec_ms = (time.perf_counter() - t1) * 1000.0
        return CompileResultPy(run.returncode, exe, None, run.stdout, compile_ms, exec_ms)


class AllToolSudo:
    """Uses liballtool_sudo.so when present, else plain sudo subprocess."""

    def __init__(self):
        self._lib = _try_load("liballtool_sudo")

    @property
    def available(self) -> bool:
        return self._lib is not None

    def run_with_creds(self, username: str, encrypted_password: str, command: str) -> tuple:
        if self._lib is None:
            raise RuntimeError("sudo C library not available")
        output = ctypes.c_char_p()
        ret = self._lib.alltool_sudo_run_with_creds(
            username.encode(), encrypted_password.encode(), command.encode(), ctypes.byref(output)
        )
        stdout = output.value.decode() if output.value else ""
        if output.value:
            ctypes.CDLL(None).free(output)
        return ret, stdout

    def prompt_credentials(self, prompt: str = "Password") -> tuple:
        if self._lib is None:
            raise RuntimeError("sudo C library not available")
        username = ctypes.c_char_p()
        password = ctypes.c_char_p()
        ret = self._lib.alltool_sudo_prompt_credentials(prompt.encode(), ctypes.byref(username), ctypes.byref(password))
        if ret != 0:
            raise RuntimeError("Failed to get credentials")
        try:
            return username.value.decode(), password.value.decode()
        finally:
            ctypes.CDLL(None).free(username)
            ctypes.CDLL(None).free(password)

    def verify_password(self, encrypted: str, salt: str, password: str) -> bool:
        if self._lib is None:
            return False
        return self._lib.alltool_sudo_verify_password(encrypted.encode(), salt.encode(), password.encode()) == 0

    def cache_credentials(self, config_path: str, username: str, password: str) -> bool:
        if self._lib is None:
            return False
        return self._lib.alltool_sudo_cache_credentials(config_path.encode(), username.encode(), password.encode()) == 0

    def load_credentials(self, config_path: str) -> Optional[Dict[str, str]]:
        if self._lib is not None:
            creds = SudoCreds()
            ret = self._lib.alltool_sudo_load_credentials(config_path.encode(), ctypes.byref(creds))
            if ret != 0:
                return None
            try:
                return {
                    "username": creds.username.decode() if creds.username else "",
                    "encrypted_password": creds.encrypted_password.decode() if creds.encrypted_password else "",
                    "salt": creds.salt.decode() if creds.salt else "",
                    "cached": creds.cached,
                }
            finally:
                self._lib.alltool_sudo_free_creds(ctypes.byref(creds))
        # Pure-Python fallback: read the JSON the C lib would have managed.
        try:
            with open(config_path) as f:
                conf = json.load(f)
            sudo = conf.get("sudo")
            if isinstance(sudo, dict) and sudo.get("cached"):
                return {"username": sudo.get("username", ""),
                        "encrypted_password": sudo.get("encrypted_password", ""),
                        "salt": sudo.get("salt", ""),
                        "cached": True}
        except (OSError, ValueError):
            pass
        return None

    def clear_cache(self, config_path: str) -> bool:
        if self._lib is not None:
            return self._lib.alltool_sudo_clear_cache(config_path.encode()) == 0
        # Fallback: ask alltool_runner (Makefile uninstall uses it), else edit JSON.
        runner = LIB_DIR / "alltool_runner"
        if runner.exists():
            try:
                subprocess.run([str(runner), "sudo-clear"], capture_output=True, check=False)
            except OSError:
                pass
        try:
            with open(config_path) as f:
                conf = json.load(f)
            if "sudo" in conf:
                conf["sudo"] = {"cached": False}
                with open(config_path, "w") as f:
                    json.dump(conf, f, indent=2)
                return True
        except (OSError, ValueError):
            pass
        return False


_DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "2.0.0",
    "bin_dir": str(HOME_DIR / "bin"),
    "cache_dir": str(HOME_DIR / "cache"),
    "logs_dir": str(HOME_DIR / "logs"),
}


def _load_json_first_hit(paths: List[Path]) -> Optional[Dict[str, Any]]:
    for p in paths:
        try:
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (OSError, ValueError):
            continue
    return None


def load_config() -> Dict[str, Any]:
    global _config_cache
    if _config_cache is not None:
        return dict(_config_cache)
    data = _load_json_first_hit([HOME_DIR / ".confs.json", REPO_ROOT / ".confs.json"])
    if data is None:
        data = dict(_DEFAULT_CONFIG)
    _config_cache = data
    return dict(data)


def save_config(config: Dict[str, Any]):
    global _config_cache
    _config_cache = dict(config)
    config_path = HOME_DIR / ".confs.json"
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except OSError:
        pass


def load_help(lang: str = "en") -> Dict[str, Any]:
    if lang in _help_cache:
        return _help_cache[lang]
    data = _load_json_first_hit([HOME_DIR / ".help.json", REPO_ROOT / ".help.json"])
    if data is None:
        data = {"commands": {}}
    for info in data.get("commands", {}).values():
        if isinstance(info, dict) and "lang" in info and lang in info["lang"]:
            info["description"] = info["lang"][lang]
    _help_cache[lang] = data
    return data


def get_installed_files() -> List[str]:
    try:
        return list(load_config().get("installed_files", []))
    except (AttributeError, TypeError):
        return []
