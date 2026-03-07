"""
Backup and Restore for the RAG pipeline database.

Backs up:
  - chroma_db/          (vector database)
  - output/chunks.json           (text chunks)
  - output/embedded_chunks.json  (chunks + embeddings)

Usage:
  python backup_restore.py backup
  python backup_restore.py backup --output-dir /mnt/backups
  python backup_restore.py restore backups/rag_backup_20260227_143000.tar.gz
  python backup_restore.py list
  python backup_restore.py list --output-dir /mnt/backups
"""

import argparse
import os
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path

# --- Paths relative to this script ---
BASE_DIR = Path(__file__).parent.resolve()
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
OUTPUT_DIR = BASE_DIR / "output"
CHUNKS_FILE = OUTPUT_DIR / "chunks.json"
EMBEDDED_FILE = OUTPUT_DIR / "embedded_chunks.json"

DEFAULT_BACKUP_DIR = BASE_DIR / "backups"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _human_size(path: Path) -> str:
    """Return a human-readable size string for a file or directory."""
    if path.is_dir():
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    else:
        total = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


def _add_to_tar(tar: tarfile.TarFile, path: Path, arcname: str):
    """Add a file or directory to a tar archive."""
    if path.exists():
        tar.add(path, arcname=arcname)
        print(f"  + {arcname}  ({_human_size(path)})")
    else:
        print(f"  ! Skipping {arcname} — not found")


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def do_backup(backup_dir: Path) -> Path:
    """Create a compressed tar backup of the RAG database files."""
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = backup_dir / f"rag_backup_{timestamp}.tar.gz"

    print(f"\nCreating backup: {archive_path}")

    with tarfile.open(archive_path, "w:gz") as tar:
        _add_to_tar(tar, CHROMA_DB_DIR, "chroma_db")
        _add_to_tar(tar, CHUNKS_FILE, "output/chunks.json")
        _add_to_tar(tar, EMBEDDED_FILE, "output/embedded_chunks.json")

    size = _human_size(archive_path)
    print(f"\nBackup complete: {archive_path}  ({size})")
    return archive_path


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def do_restore(archive_path: Path, force: bool = False):
    """Restore from a backup archive."""
    if not archive_path.exists():
        print(f"Error: archive not found: {archive_path}")
        sys.exit(1)

    if not tarfile.is_tarfile(archive_path):
        print(f"Error: not a valid tar file: {archive_path}")
        sys.exit(1)

    # Safety check — warn if live data exists
    if not force:
        existing = [p for p in (CHROMA_DB_DIR, CHUNKS_FILE, EMBEDDED_FILE) if p.exists()]
        if existing:
            print("\nWarning: the following will be overwritten:")
            for p in existing:
                print(f"  - {p}  ({_human_size(p)})")
            answer = input("\nContinue? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted.")
                sys.exit(0)

    print(f"\nRestoring from: {archive_path}")

    # Remove existing data before extracting
    if CHROMA_DB_DIR.exists():
        print(f"  Removing {CHROMA_DB_DIR} ...")
        shutil.rmtree(CHROMA_DB_DIR)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            tar.extract(member, path=BASE_DIR)
            print(f"  Extracted: {member.name}")

    print("\nRestore complete.")
    print("  Restart the MCP server to pick up the restored database:")
    print("    sudo systemctl restart mcp-rag")


# ---------------------------------------------------------------------------
# List backups
# ---------------------------------------------------------------------------

def do_list(backup_dir: Path):
    """List available backups."""
    if not backup_dir.exists():
        print(f"No backup directory found at: {backup_dir}")
        return

    archives = sorted(backup_dir.glob("rag_backup_*.tar.gz"))
    if not archives:
        print(f"No backups found in: {backup_dir}")
        return

    print(f"\nBackups in {backup_dir}:\n")
    print(f"  {'File':<45}  {'Size':>8}")
    print(f"  {'-'*45}  {'-'*8}")
    for a in archives:
        print(f"  {a.name:<45}  {_human_size(a):>8}")

    print(f"\nTotal: {len(archives)} backup(s)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Backup and restore the RAG pipeline database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # backup
    p_backup = sub.add_parser("backup", help="Create a new backup")
    p_backup.add_argument(
        "--output-dir", type=Path, default=DEFAULT_BACKUP_DIR,
        help=f"Directory to store backups (default: {DEFAULT_BACKUP_DIR})"
    )

    # restore
    p_restore = sub.add_parser("restore", help="Restore from a backup archive")
    p_restore.add_argument("archive", type=Path, help="Path to .tar.gz backup file")
    p_restore.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompt"
    )

    # list
    p_list = sub.add_parser("list", help="List available backups")
    p_list.add_argument(
        "--output-dir", type=Path, default=DEFAULT_BACKUP_DIR,
        help=f"Backup directory to list (default: {DEFAULT_BACKUP_DIR})"
    )

    args = parser.parse_args()

    if args.command == "backup":
        do_backup(args.output_dir)
    elif args.command == "restore":
        do_restore(args.archive, force=args.force)
    elif args.command == "list":
        do_list(args.output_dir)


if __name__ == "__main__":
    main()
