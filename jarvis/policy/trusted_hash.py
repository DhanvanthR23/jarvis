import hashlib

TRUSTED_HASH: str = ''

def compute_and_store_hash(manifest_path: str, hash_file_path: str):
    with open(manifest_path, "rb") as f:
        content = f.read()
    file_hash = hashlib.sha256(content).hexdigest()
    with open(hash_file_path, "w") as f:
        f.write(file_hash)

def load_trusted_hash(hash_file_path: str) -> str:
    with open(hash_file_path, "r") as f:
        return f.read().strip()
