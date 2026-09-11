import ctypes
import os
import json
import platform
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

HOME_DIR = Path.home() / ".config" / "alltool"
BIN_DIR = HOME_DIR / "bin"
LIB_DIR = BIN_DIR

_shm_lib = None
_compiler_lib = None
_sudo_lib = None

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

def _load_libraries():
    global _shm_lib, _compiler_lib, _sudo_lib
    if _shm_lib is not None:
        return

    lib_ext = ".so" if platform.system() == "Linux" else ".dylib"

    _shm_lib = ctypes.CDLL(str(LIB_DIR / f"liballtool_shm{lib_ext}"))
    _compiler_lib = ctypes.CDLL(str(LIB_DIR / f"liballtool_compiler{lib_ext}"))
    _sudo_lib = ctypes.CDLL(str(LIB_DIR / f"liballtool_sudo{lib_ext}"))

    _setup_shm_bindings()
    _setup_compiler_bindings()
    _setup_sudo_bindings()

def _setup_shm_bindings():
    _shm_lib.alltool_shm_init.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    _shm_lib.alltool_shm_init.restype = ctypes.c_int

    _shm_lib.alltool_shm_attach.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    _shm_lib.alltool_shm_attach.restype = ctypes.c_int

    _shm_lib.alltool_shm_register_process.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int32]
    _shm_lib.alltool_shm_register_process.restype = ctypes.c_int

    _shm_lib.alltool_shm_wait_predecessor.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _shm_lib.alltool_shm_wait_predecessor.restype = ctypes.c_int

    _shm_lib.alltool_shm_send_payload.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    _shm_lib.alltool_shm_send_payload.restype = ctypes.c_int

    _shm_lib.alltool_shm_recv_payload.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    _shm_lib.alltool_shm_recv_payload.restype = ctypes.c_int

    _shm_lib.alltool_shm_mark_done.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _shm_lib.alltool_shm_mark_done.restype = ctypes.c_int

    _shm_lib.alltool_shm_detach.argtypes = [ctypes.c_void_p]
    _shm_lib.alltool_shm_detach.restype = None

    _shm_lib.alltool_shm_cleanup.argtypes = [ctypes.c_char_p]
    _shm_lib.alltool_shm_cleanup.restype = None

def _setup_compiler_bindings():
    _compiler_lib.alltool_detect_language.argtypes = [ctypes.c_char_p]
    _compiler_lib.alltool_detect_language.restype = ctypes.c_int

    _compiler_lib.alltool_lang_to_string.argtypes = [ctypes.c_int]
    _compiler_lib.alltool_lang_to_string.restype = ctypes.c_char_p

    _compiler_lib.alltool_get_compiler.argtypes = [ctypes.c_int]
    _compiler_lib.alltool_get_compiler.restype = ctypes.c_char_p

    _compiler_lib.alltool_compile_and_run.argtypes = [ctypes.POINTER(CompileOpts), ctypes.POINTER(CompileResult)]
    _compiler_lib.alltool_compile_and_run.restype = ctypes.c_int

    _compiler_lib.alltool_free_result.argtypes = [ctypes.POINTER(CompileResult)]
    _compiler_lib.alltool_free_result.restype = None

    _compiler_lib.alltool_get_cache_path.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _compiler_lib.alltool_get_cache_path.restype = ctypes.c_char_p

def _setup_sudo_bindings():
    _sudo_lib.alltool_sudo_prompt_credentials.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_char_p)]
    _sudo_lib.alltool_sudo_prompt_credentials.restype = ctypes.c_int

    _sudo_lib.alltool_sudo_encrypt_password.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    _sudo_lib.alltool_sudo_encrypt_password.restype = ctypes.c_int

    _sudo_lib.alltool_sudo_verify_password.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    _sudo_lib.alltool_sudo_verify_password.restype = ctypes.c_int

    _sudo_lib.alltool_sudo_generate_salt.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
    _sudo_lib.alltool_sudo_generate_salt.restype = ctypes.c_int

    _sudo_lib.alltool_sudo_run_with_creds.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    _sudo_lib.alltool_sudo_run_with_creds.restype = ctypes.c_int

    _sudo_lib.alltool_sudo_cache_credentials.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    _sudo_lib.alltool_sudo_cache_credentials.restype = ctypes.c_int

    _sudo_lib.alltool_sudo_load_credentials.argtypes = [ctypes.c_char_p, ctypes.POINTER(SudoCreds)]
    _sudo_lib.alltool_sudo_load_credentials.restype = ctypes.c_int

    _sudo_lib.alltool_sudo_free_creds.argtypes = [ctypes.POINTER(SudoCreds)]
    _sudo_lib.alltool_sudo_free_creds.restype = None

    _sudo_lib.alltool_sudo_clear_cache.argtypes = [ctypes.c_char_p]
    _sudo_lib.alltool_sudo_clear_cache.restype = ctypes.c_int

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
        _load_libraries()
        self.name = name.encode()
        self.size = size
        self.ctx = ctypes.create_string_buffer(ctypes.sizeof(ctypes.c_void_p) * 4)
        self._init()

    def _init(self):
        ret = _shm_lib.alltool_shm_init(self.name, self.size)
        if ret != 0:
            raise RuntimeError(f"Failed to initialize SHM: {ret}")
        ret = _shm_lib.alltool_shm_attach(self.name, self.ctx)
        if ret != 0:
            raise RuntimeError(f"Failed to attach to SHM: {ret}")

    def register_process(self, pid: int, predecessor_idx: int) -> int:
        return _shm_lib.alltool_shm_register_process(self.ctx, pid, predecessor_idx)

    def wait_predecessor(self, timeout_ms: int = -1) -> int:
        return _shm_lib.alltool_shm_wait_predecessor(self.ctx, timeout_ms)

    def send_payload(self, data: bytes) -> int:
        return _shm_lib.alltool_shm_send_payload(self.ctx, data, len(data))

    def recv_payload(self, buffer_size: int = 4096) -> bytes:
        buffer = ctypes.create_string_buffer(buffer_size)
        size = ctypes.c_size_t(buffer_size)
        ret = _shm_lib.alltool_shm_recv_payload(self.ctx, buffer, ctypes.byref(size))
        if ret != 0:
            return b""
        return buffer.raw[:size.value]

    def mark_done(self, status: int) -> int:
        return _shm_lib.alltool_shm_mark_done(self.ctx, status)

    def detach(self):
        _shm_lib.alltool_shm_detach(self.ctx)

    def cleanup(self):
        _shm_lib.alltool_shm_cleanup(self.name)

class AllToolCompiler:
    def __init__(self):
        _load_libraries()

    def detect_language(self, filename: str) -> int:
        return _compiler_lib.alltool_detect_language(filename.encode())

    def lang_to_string(self, lang: int) -> str:
        return _compiler_lib.alltool_lang_to_string(lang).decode()

    def get_compiler(self, lang: int) -> str:
        return _compiler_lib.alltool_get_compiler(lang).decode()

    def compile_and_run(self, source_path: str, cache_dir: str = None, temp_mode: bool = False,
                       compiler_flags: str = "-O2 -pipe", output_path: str = None) -> CompileResultPy:
        opts = CompileOpts()
        opts.source_path = source_path.encode()
        opts.output_path = output_path.encode() if output_path else None
        opts.cache_dir = cache_dir.encode() if cache_dir else str(HOME_DIR / "cache").encode()
        opts.temp_mode = temp_mode
        opts.compiler_flags = compiler_flags.encode()
        opts.lang = self.detect_language(source_path)

        result = CompileResult()
        ret = _compiler_lib.alltool_compile_and_run(ctypes.byref(opts), ctypes.byref(result))

        out = CompileResultPy(
            exit_code=result.exit_code,
            output_path=result.output_path.decode() if result.output_path else None,
            error_message=result.error_message.decode() if result.error_message else None,
            exec_output=result.exec_output.decode() if result.exec_output else None,
            compile_time_ms=result.compile_time_ms,
            exec_time_ms=result.exec_time_ms
        )
        _compiler_lib.alltool_free_result(ctypes.byref(result))
        return out

class AllToolSudo:
    def __init__(self):
        _load_libraries()
        self._lib = _sudo_lib

    def run_with_creds(self, username: str, encrypted_password: str, command: str) -> tuple:
        output = ctypes.c_char_p()
        ret = _sudo_lib.alltool_sudo_run_with_creds(
            username.encode(), encrypted_password.encode(), command.encode(), ctypes.byref(output)
        )
        stdout = output.value.decode() if output.value else ""
        if output.value:
            ctypes.CDLL(None).free(output)
        return ret, stdout

    def prompt_credentials(self, prompt: str = "Password") -> tuple:
        username = ctypes.c_char_p()
        password = ctypes.c_char_p()
        ret = _sudo_lib.alltool_sudo_prompt_credentials(prompt.encode(), ctypes.byref(username), ctypes.byref(password))
        if ret != 0:
            raise RuntimeError("Failed to get credentials")
        try:
            return username.value.decode(), password.value.decode()
        finally:
            ctypes.CDLL(None).free(username)
            ctypes.CDLL(None).free(password)

    def verify_password(self, encrypted: str, salt: str, password: str) -> bool:
        return _sudo_lib.alltool_sudo_verify_password(encrypted.encode(), salt.encode(), password.encode()) == 0

    def cache_credentials(self, config_path: str, username: str, password: str) -> bool:
        return _sudo_lib.alltool_sudo_cache_credentials(config_path.encode(), username.encode(), password.encode()) == 0

    def load_credentials(self, config_path: str) -> Optional[Dict[str, str]]:
        creds = SudoCreds()
        ret = _sudo_lib.alltool_sudo_load_credentials(config_path.encode(), ctypes.byref(creds))
        if ret != 0:
            return None
        try:
            return {
                "username": creds.username.decode() if creds.username else "",
                "encrypted_password": creds.encrypted_password.decode() if creds.encrypted_password else "",
                "salt": creds.salt.decode() if creds.salt else "",
                "cached": creds.cached
            }
        finally:
            _sudo_lib.alltool_sudo_free_creds(ctypes.byref(creds))

    def clear_cache(self, config_path: str) -> bool:
        return _sudo_lib.alltool_sudo_clear_cache(config_path.encode()) == 0

def load_config() -> Dict[str, Any]:
    config_path = HOME_DIR / ".confs.json"
    with open(config_path) as f:
        return json.load(f)

def save_config(config: Dict[str, Any]):
    config_path = HOME_DIR / ".confs.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

def load_help(lang: str = "en") -> Dict[str, Any]:
    help_path = HOME_DIR / ".help.json"
    with open(help_path) as f:
        data = json.load(f)
    for cmd, info in data.get("commands", {}).items():
        if "lang" in info and lang in info["lang"]:
            info["description"] = info["lang"][lang]
    return data

def get_installed_files() -> List[str]:
    config = load_config()
    return config.get("installed_files", [])