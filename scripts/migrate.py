"""Run Alembic migrations programmatically."""
import subprocess, sys

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    if cmd == "upgrade":
        subprocess.run(["alembic", "upgrade", "head"], check=True)
    elif cmd == "downgrade":
        rev = sys.argv[2] if len(sys.argv) > 2 else "-1"
        subprocess.run(["alembic", "downgrade", rev], check=True)
    elif cmd == "revision":
        msg = sys.argv[2] if len(sys.argv) > 2 else "auto migration"
        subprocess.run(["alembic", "revision", "--autogenerate", "-m", msg], check=True)
    elif cmd == "history":
        subprocess.run(["alembic", "history", "--verbose"], check=True)
    elif cmd == "current":
        subprocess.run(["alembic", "current"], check=True)
    else:
        print(f"Usage: python scripts/migrate.py [upgrade|downgrade|revision|history|current]")
        sys.exit(1)

if __name__ == "__main__":
    main()
