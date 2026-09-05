"""Utility da riga di comando.

    docker compose run --rm backend python -m app.cli hash-password
    docker compose run --rm backend python -m app.cli secret
"""

import getpass
import sys

from .security import generate_token, hash_password


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "hash-password":
        pw = getpass.getpass("Password owner: ")
        if pw != getpass.getpass("Conferma: "):
            print("Le password non coincidono.", file=sys.stderr)
            return 1
        print(hash_password(pw))
        return 0
    if cmd == "secret":
        print(generate_token())
        return 0
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
