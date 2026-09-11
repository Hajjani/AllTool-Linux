from .base import command, ToolBase
import hashlib
import string
import random
import sys
import os

@command("psg", aliases=["passgen"], help_text="Generate secure password")
def password_generator(args: list):
    if not args:
        print("Usage: alltool psg <length> [nose] [nos] [not] [nol]")
        print("  nose: no lowercase")
        print("  nos: no uppercase")
        print("  not: no digits")
        print("  nol: no special characters")
        return 1

    try:
        length = int(args[0])
    except ValueError:
        print("❌ Error: Length must be a number.")
        return 1

    use_special = "nol" not in args
    use_digits = "not" not in args
    use_upper = "nos" not in args
    use_lower = "nose" not in args

    chars = ""
    if use_lower:
        chars += string.ascii_lowercase
    if use_upper:
        chars += string.ascii_uppercase
    if use_digits:
        chars += string.digits
    if use_special:
        chars += string.punctuation

    if not chars:
        print("❌ Error: No character types selected. Use at least one character set.")
        return 1

    password = "".join(random.choice(chars) for _ in range(length))
    print(f"✅ Generated password: {password}")
    return 0

@command("hs", aliases=["hash"], help_text="Calculate file hash (md5, sha1, sha256, sha512, blake2b, blake2s)")
def file_hash(args: list):
    if len(args) != 2:
        print("Usage: alltool hs <file> <type: md5|sha1|sha256|sha512|blake2b|blake2s>")
        return 1

    file_path = args[0]
    hash_type = args[1].lower()

    if not os.path.isfile(file_path):
        print(f"❌ File not found: {file_path}")
        return 1

    hash_map = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
        "blake2b": hashlib.blake2b,
        "blake2s": hashlib.blake2s,
    }

    if hash_type not in hash_map:
        print(f"❌ Unsupported hash type: {hash_type}")
        print("Supported: md5, sha1, sha256, sha512, blake2b, blake2s")
        return 1

    with open(file_path, "rb") as f:
        data = f.read()
        hash_obj = hash_map[hash_type]()
        hash_obj.update(data)
        print(f"🔐 {hash_type.upper()} hash of '{file_path}':\n{hash_obj.hexdigest()}")
    return 0