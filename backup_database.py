import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def load_env():
    if load_dotenv and ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH)


def fail(message: str, exit_code: int = 1):
    print(f"Erro: {message}", file=sys.stderr)
    sys.exit(exit_code)


def run_command(command, env=None, capture=False, cwd=None):
    try:
        result = subprocess.run(
            command,
            env=env,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=capture,
        )
        return result.stdout.strip() if capture else ""
    except FileNotFoundError:
        fail(f"Comando não encontrado: {command[0]}")
    except subprocess.CalledProcessError as exc:
        if capture and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        fail(f"Falha ao executar comando: {' '.join(command)}")


def get_database_uri():
    """
    Em produção, prioriza DATABASE_URI/DATABASE_URL.
    DEV_DATABASE_URI fica por último para evitar backup acidental do banco errado.
    """
    db_uri = (
        os.getenv("DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or os.getenv("DEV_DATABASE_URI")
    )

    if not db_uri:
        fail("Nenhuma URI encontrada. Defina DATABASE_URI, DATABASE_URL ou DEV_DATABASE_URI.")

    return db_uri


def sanitize_database_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.password:
        netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
    else:
        netloc = parsed.netloc
    return urlunparse(parsed._replace(netloc=netloc))


def parse_db_uri(uri: str):
    parsed = urlparse(uri)

    if not parsed.path or parsed.path == "/":
        fail("DATABASE_URI não contém nome do banco.")

    return {
        "dbname": parsed.path[1:],
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
    }


def resolve_upload_folder() -> Path | None:
    upload_folder = os.getenv("UPLOAD_FOLDER", "api/static/uploads")
    path = Path(upload_folder)

    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.exists():
        print(f"Aviso: pasta de uploads não encontrada: {path}")
        return None

    return path


def get_git_commit():
    try:
        return run_command(["git", "rev-parse", "HEAD"], capture=True, cwd=BASE_DIR)
    except SystemExit:
        return "sem_git"


def get_alembic_revision(env):
    try:
        return run_command(
            ["python", "-m", "flask", "--app", "run.py", "db", "current"],
            env=env,
            capture=True,
            cwd=BASE_DIR,
        )
    except SystemExit:
        return "indisponivel"


def get_python_version():
    return sys.version.split()[0]


def get_postgres_version():
    try:
        return run_command(["psql", "--version"], capture=True)
    except SystemExit:
        return "indisponivel"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def write_checksums(backup_dir: Path, files: list[Path]):
    checksum_path = backup_dir / "checksums.sha256"

    with checksum_path.open("w", encoding="utf-8", newline="\n") as output:
        for file_path in files:
            digest = sha256_file(file_path)
            output.write(f"{digest}  {file_path.name}\n")

    return checksum_path


def create_database_dump(db_uri: str, backup_dir: Path) -> Path:
    config = parse_db_uri(db_uri)
    dump_path = backup_dir / "database.dump"

    print(f"Gerando dump do banco '{config['dbname']}' em '{config['host']}'...")
    print(f"Destino: {dump_path}")

    env = os.environ.copy()
    if config["password"]:
        env["PGPASSWORD"] = config["password"]

    command = [
        "pg_dump",
        "-h",
        str(config["host"]),
        "-p",
        str(config["port"]),
        "-U",
        str(config["user"]),
        "-F",
        "c",
        "-f",
        str(dump_path),
        str(config["dbname"]),
    ]

    run_command(command, env=env)

    if not dump_path.exists() or dump_path.stat().st_size == 0:
        fail("database.dump não foi criado ou está vazio.")

    return dump_path


def create_uploads_archive(backup_dir: Path) -> Path | None:
    upload_path = resolve_upload_folder()

    if upload_path is None:
        return None

    archive_path = backup_dir / "uploads.tar.gz"

    print(f"Compactando uploads: {upload_path}")
    print(f"Destino: {archive_path}")

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(upload_path, arcname="uploads")

    if not archive_path.exists() or archive_path.stat().st_size == 0:
        fail("uploads.tar.gz não foi criado ou está vazio.")

    return archive_path


def write_manifest(
    backup_dir: Path,
    db_uri: str,
    dump_path: Path,
    uploads_path: Path | None,
    env,
):
    manifest = {
        "app": "api-assistencias",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": os.getenv("FLASK_ENV", "unknown"),
        "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "database_uri_sanitized": sanitize_database_uri(db_uri),
        "database_dump": {
            "file": dump_path.name,
            "size_bytes": dump_path.stat().st_size,
        },
        "uploads": {
            "file": uploads_path.name if uploads_path else None,
            "size_bytes": uploads_path.stat().st_size if uploads_path else 0,
            "included": uploads_path is not None,
        },
        "git_commit": get_git_commit(),
        "alembic_revision": get_alembic_revision(env),
        "python_version": get_python_version(),
        "postgres_version": get_postgres_version(),
    }

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return manifest_path


def create_backup():
    load_env()

    db_uri = get_database_uri()

    backup_root = Path(os.getenv("BACKUP_DIR", "backups"))
    if not backup_root.is_absolute():
        backup_root = BASE_DIR / backup_root

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = backup_root / f"prod_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    print(f"Iniciando backup em: {backup_dir}")

    env = os.environ.copy()
    env["DATABASE_URI"] = db_uri
    env.setdefault("FLASK_APP", "run.py")

    dump_path = create_database_dump(db_uri, backup_dir)
    uploads_path = create_uploads_archive(backup_dir)
    manifest_path = write_manifest(backup_dir, db_uri, dump_path, uploads_path, env)

    files_for_checksum = [dump_path, manifest_path]
    if uploads_path:
        files_for_checksum.append(uploads_path)

    checksum_path = write_checksums(backup_dir, files_for_checksum)

    print("")
    print("Backup concluído com sucesso.")
    print(f"Pasta: {backup_dir}")
    print(f"- {dump_path.name}")
    if uploads_path:
        print(f"- {uploads_path.name}")
    print(f"- {manifest_path.name}")
    print(f"- {checksum_path.name}")

    return str(backup_dir)


if __name__ == "__main__":
    create_backup()