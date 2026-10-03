"""The editor the Git sandbox gives git (GIT_EDITOR / GIT_SEQUENCE_EDITOR).

Git calls it with a file to edit: a commit message, or a rebase todo list.
It names the file so the player can edit it in their own editor, then waits
for Enter. With no terminal (tests, piped input) it returns at once, which
accepts the file as git wrote it."""

import sys


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "(no file)"
    print(f"\n[editor] git opened: {path}")
    print("  Edit and save it in your own editor, then press Enter here. Type 'abort' to cancel.")
    try:
        answer = input()
    except EOFError:
        return 0
    return 1 if answer.strip().lower() == "abort" else 0


if __name__ == "__main__":
    sys.exit(main())
