"""Docker-free local PostgreSQL 16 + pgvector for Windows.

Uses the prebuilt PostgreSQL+pgvector binaries shipped inside the `pgserver`
wheel on PyPI. They are unpacked into ./.local-postgres (git-ignored); nothing
is installed system-wide and no Windows service is created.

    python scripts/local_postgres.py setup    # download, initdb, create 'ragdb', start
    python scripts/local_postgres.py start
    python scripts/local_postgres.py stop
    python scripts/local_postgres.py status

The server listens on localhost:5432 with user/password postgres/postgres,
matching DATABASE_URL in .env.example. Prefer Docker (docker compose up -d)
if you have it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PG_HOME = ROOT / ".local-postgres"
BIN = PG_HOME / "bin"
DATA = PG_HOME / "data"
LOG = PG_HOME / "postgres.log"
PORT = "5432"
USER = PASSWORD = "postgres"
DB = "ragdb"
WHEEL_SPEC = "pgserver==0.1.4"  # PostgreSQL 16.2 + pgvector 0.6.2


def exe(name: str) -> str:
    return str(BIN / (name + (".exe" if os.name == "nt" else "")))


def run(*cmd: str, check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, **kw)


def psql(sql: str, db: str = "postgres") -> None:
    env = {**os.environ, "PGPASSWORD": PASSWORD}
    run(exe("psql"), "-h", "localhost", "-p", PORT, "-U", USER, "-d", db, "-v", "ON_ERROR_STOP=1",
        "-c", sql, env=env)


def download_binaries() -> None:
    if (BIN / "postgres.exe").exists() or (BIN / "postgres").exists():
        print("PostgreSQL binaries already present.")
        return
    if os.name != "nt":
        sys.exit("This helper targets Windows. On macOS/Linux use: docker compose up -d")
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Downloading {WHEEL_SPEC} (PostgreSQL + pgvector binaries, ~20 MB)...")
        # The binaries are version-independent; we only borrow them from the cp312 wheel.
        run(sys.executable, "-m", "pip", "download", WHEEL_SPEC, "--no-deps", "--only-binary=:all:",
            "--python-version", "3.12", "--platform", "win_amd64", "-d", tmp)
        wheel = next(Path(tmp).glob("pgserver-*.whl"))
        prefix = "pgserver/pginstall/"
        with zipfile.ZipFile(wheel) as zf:
            for name in zf.namelist():
                if name.startswith(prefix) and not name.endswith("/"):
                    target = PG_HOME / name[len(prefix):]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
    print(f"Unpacked to {PG_HOME}")


def is_running() -> bool:
    if not DATA.exists():
        return False
    return run(exe("pg_ctl"), "-D", str(DATA), "status", check=False,
               stdout=subprocess.DEVNULL).returncode == 0


def start() -> None:
    if is_running():
        print("PostgreSQL is already running.")
        return
    run(exe("pg_ctl"), "-D", str(DATA), "-l", str(LOG), "-w",
        "-o", f"-p {PORT} -c listen_addresses=localhost", "start")


def setup() -> None:
    download_binaries()
    if not DATA.exists():
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
            f.write(PASSWORD)
        try:
            run(exe("initdb"), "-D", str(DATA), "-U", USER, f"--pwfile={f.name}",
                "-A", "scram-sha-256", "-E", "UTF8", "--locale=C")
        finally:
            os.unlink(f.name)
    start()
    env = {**os.environ, "PGPASSWORD": PASSWORD}
    exists = run(exe("psql"), "-h", "localhost", "-p", PORT, "-U", USER, "-tAc",
                 f"SELECT 1 FROM pg_database WHERE datname='{DB}'",
                 env=env, capture_output=True, text=True).stdout.strip()
    if exists != "1":
        psql(f"CREATE DATABASE {DB}")
    psql("CREATE EXTENSION IF NOT EXISTS vector", db=DB)
    print(f"Ready: postgresql+psycopg://{USER}:{PASSWORD}@localhost:{PORT}/{DB} (pgvector enabled)")


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "setup":
        setup()
    elif action == "start":
        start()
    elif action == "stop":
        if is_running():
            run(exe("pg_ctl"), "-D", str(DATA), "-w", "stop")
        else:
            print("PostgreSQL is not running.")
    elif action == "status":
        print("running" if is_running() else "not running")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
