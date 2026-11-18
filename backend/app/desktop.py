"""AutoStock as a normal Windows app, without Docker (built into AutoStock.exe by windows/build.ps1).

Double-click the AutoStock icon:
1. If AutoStock is already running on this PC, it only opens the window.
2. Otherwise it starts the shop's database (PostgreSQL, shipped inside the app, run only while
   AutoStock runs), updates it if a new version was installed (a backup first), starts the
   server, then opens AutoStock in its own window (Microsoft Edge's app mode, already on Windows).
3. Closing the window does not stop AutoStock: the other computers and phones in the shop keep
   using it at http://<this PC's name>:8765. "Stop AutoStock" in the Start menu stops it.

Everything the shop owns lives in %LOCALAPPDATA%\\AutoStock (the database, settings, logs), and
the backups in Documents\\AutoStock backups. Uninstalling the app never deletes them.
Nothing here needs the internet. Only Ask's online assistant does, when the owner turns it on.

    AutoStock.exe               start if needed, then open the window
    AutoStock.exe --background  start without a window (used when Windows starts)
    AutoStock.exe --stop        stop AutoStock and its database
    AutoStock.exe --restore F   put backup F back (from the backups folder)
"""

import logging
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8765
DATABASE_PORT = 54329
DATABASE_USER = "autostock"
HIDE_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no black box flashing on Windows
log = logging.getLogger("autostock.desktop")


def app_folder() -> Path:
    """Where the program's own files are: inside AutoStock.exe's folder once built, backend/ while developing."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def data_folder() -> Path:
    if os.environ.get("AUTOSTOCK_DATA"):  # tests and developers
        return Path(os.environ["AUTOSTOCK_DATA"])
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "AutoStock"


def backups_folder() -> Path:
    if os.environ.get("AUTOSTOCK_BACKUPS"):
        return Path(os.environ["AUTOSTOCK_BACKUPS"])
    return Path.home() / "Documents" / "AutoStock backups"


def pg_bin() -> Path:
    """PostgreSQL's programs: shipped in pgsql/bin, or PG_BIN while developing on Linux."""
    shipped = app_folder() / "pgsql" / "bin"
    return shipped if shipped.is_dir() else Path(os.environ.get("PG_BIN", "/usr/lib/postgresql/16/bin"))


def tool(name: str) -> str:
    exe = pg_bin() / (name + ".exe" if os.name == "nt" else name)
    return str(exe)


def read_settings(file: Path) -> dict[str, str]:
    settings = {}
    if file.is_file():
        for line in file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                settings[key.strip()] = value.strip()
    return settings


def settings() -> dict[str, str]:
    """settings.env in the data folder, made on the first start with a random database password.
    The owner may add GROQ_API_KEY=... there to turn on Ask's online assistant."""
    file = data_folder() / "settings.env"
    found = read_settings(file)
    if "DATABASE_PASSWORD" not in found:
        found["DATABASE_PASSWORD"] = secrets.token_urlsafe(24)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            "# AutoStock settings. Keep this file: it holds the password of the shop's database.\n"
            f"DATABASE_PASSWORD={found['DATABASE_PASSWORD']}\n"
            "# Ask's online assistant (Groq, free): paste a key after the = and restart AutoStock.\n"
            "GROQ_API_KEY=\n",
            encoding="utf-8",
        )
    return found


def is_running(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as answer:
            return answer.status == 200
    except OSError:
        return False


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, creationflags=HIDE_WINDOW)


def create_database_folder(folder: Path, password: str) -> None:
    """First start only: an empty PostgreSQL database folder, password-protected."""
    password_file = folder.parent / "first-password.tmp"
    password_file.write_text(password, encoding="utf-8")
    try:
        made = run(tool("initdb"), "-D", str(folder), "-U", DATABASE_USER, f"--pwfile={password_file}",
                   "-E", "UTF8", "--no-locale", "--auth=scram-sha-256")
    finally:
        password_file.unlink(missing_ok=True)
    if made.returncode != 0:
        shutil.rmtree(folder, ignore_errors=True)  # so the next start tries again from scratch
        raise RuntimeError(f"The database could not be created: {made.stderr.strip()}")


def start_database(password: str) -> None:
    folder = data_folder() / "database"
    if not (folder / "PG_VERSION").is_file():
        create_database_folder(folder, password)
    if run(tool("pg_ctl"), "status", "-D", str(folder)).returncode == 0:
        return  # already running (AutoStock was stopped in a hurry)
    logs = data_folder() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    # Output to a file, not a pipe: on Windows the database keeps the pipe open, so reading it never ends.
    output = logs / "database-start.log"
    with output.open("w", encoding="utf-8") as file:
        started = subprocess.run([tool("pg_ctl"), "start", "-w", "-t", "60", "-D", str(folder), "-l", str(logs / "database.log"),
                                  "-o", f"-p {DATABASE_PORT} -c listen_addresses=127.0.0.1"],
                                 stdout=file, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=HIDE_WINDOW)
    if started.returncode != 0:
        raise RuntimeError(f"The database did not start: {output.read_text(encoding='utf-8').strip()}"
                           f" (see {logs / 'database.log'})")


def stop_database() -> None:
    run(tool("pg_ctl"), "stop", "-m", "fast", "-D", str(data_folder() / "database"))


def make_shop_database(password: str) -> None:
    """The 'autostock' database inside the server, on the first start."""
    import psycopg

    with psycopg.connect(host="127.0.0.1", port=DATABASE_PORT, user=DATABASE_USER, password=password,
                         dbname="postgres", autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname = 'autostock'").fetchone():
            connection.execute("CREATE DATABASE autostock")


def set_environment(found: dict[str, str]) -> None:
    """What app.config reads. Must run before any other part of the app is imported."""
    website = app_folder() / "website"
    os.environ.update({
        "DATABASE_URL": f"postgresql+psycopg://{DATABASE_USER}:{found['DATABASE_PASSWORD']}@127.0.0.1:{DATABASE_PORT}/autostock",
        "APP_ENV": "production",
        "APP_URL": f"http://localhost:{PORT}",
        "BACKUP_DIR": str(backups_folder()),
        "PG_BIN": str(pg_bin()),
        "TZ": "Africa/Casablanca",
        "GROQ_API_KEY": found.get("GROQ_API_KEY", ""),
        "RESTORE_COMMAND": f'"{sys.executable}" --restore' if getattr(sys, "frozen", False) else "python -m app.desktop --restore",
    })
    if website.is_dir():
        os.environ["WEBSITE_DIR"] = str(website)


def open_window() -> None:
    """AutoStock in its own window (Edge app mode, on every Windows 10 and 11), else the browser."""
    address = f"http://localhost:{PORT}"
    if os.name == "nt":
        for edge in (Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
                     Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe"):
            if edge.is_file():
                subprocess.Popen([str(edge), f"--app={address}", "--window-size=1440,900"], creationflags=HIDE_WINDOW)
                return
    webbrowser.open(address)


def write_logs_to_file() -> None:
    """The built app has no console, so everything goes to logs/autostock.log (kept small)."""
    from logging.handlers import RotatingFileHandler

    logs = data_folder() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(logs / "autostock.log", maxBytes=5 * 2**20, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    if sys.stdout is None or getattr(sys, "frozen", False):
        sys.stdout = sys.stderr = open(logs / "output.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115


def serve(open_after_start: bool) -> None:
    found = settings()
    start_database(found["DATABASE_PASSWORD"])
    make_shop_database(found["DATABASE_PASSWORD"])
    set_environment(found)
    os.chdir(app_folder())  # alembic.ini and the database changes (migrations) are here

    from app import start

    problem = start.update_database()
    if problem:
        log.error(problem)
        if open_after_start:
            open_window()
        start.show_problem(problem, PORT)
        return

    import threading

    import uvicorn

    from app.main import app

    if open_after_start:
        def open_when_ready() -> None:
            for _ in range(120):
                if is_running():
                    open_window()
                    return
                time.sleep(0.5)

        threading.Thread(target=open_when_ready, daemon=True).start()
    (data_folder() / "autostock.pid").write_text(str(os.getpid()))
    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_config=None, server_header=False)
    finally:
        stop_database()
        (data_folder() / "autostock.pid").unlink(missing_ok=True)


def stop() -> None:
    pid_file = data_folder() / "autostock.pid"
    if pid_file.is_file():
        pid = int(pid_file.read_text())
        if os.name == "nt":
            run("taskkill", "/PID", str(pid), "/T", "/F")
        else:
            import signal

            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _ in range(20):
            if not is_running():
                break
            time.sleep(0.5)
        pid_file.unlink(missing_ok=True)
    stop_database()


def restore(name: str) -> None:
    found = settings()
    start_database(found["DATABASE_PASSWORD"])
    set_environment(found)
    os.chdir(app_folder())
    sys.argv = ["app.restore", name]
    from app.restore import main as restore_main

    restore_main()


def main() -> None:
    args = sys.argv[1:]
    write_logs_to_file()
    try:
        if args[:1] == ["--stop"]:
            stop()
        elif args[:1] == ["--restore"] and len(args) == 2:
            restore(args[1])
        elif is_running():
            if "--background" not in args:
                open_window()
        else:
            serve(open_after_start="--background" not in args)
    except Exception:
        log.exception("AutoStock could not start")
        raise


if __name__ == "__main__":
    main()
