"""Utility da riga di comando.

    docker compose run --rm backend python -m app.cli hash-password
    docker compose run --rm backend python -m app.cli secret

`hash-password` scrive l'hash in secrets/owner_password_hash. Non in .env:
un hash argon2 è pieno di `$` e Docker Compose li interpola, consegnando al
container un hash mutilato e un login che fallisce senza spiegare perché.
"""

import getpass
import sys
from pathlib import Path

from .security import generate_token, hash_password

SECRET_PATH = Path("/secrets/owner_password_hash")


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "hash-password":
        pw = getpass.getpass("Password owner: ")
        if pw != getpass.getpass("Conferma: "):
            print("Le password non coincidono.", file=sys.stderr)
            return 1
        digest = hash_password(pw)
        if SECRET_PATH.parent.is_dir():
            SECRET_PATH.write_text(digest + "\n")
            SECRET_PATH.chmod(0o600)
            print(f"Hash scritto in {SECRET_PATH}. Riavvia il backend.")
        else:
            print(digest)
        return 0
    if cmd == "secret":
        print(generate_token())
        return 0
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
