# PyInstaller recipe for AutoStock.exe (run by windows/build.ps1, from the repository's root).
# One folder: AutoStock.exe plus _internal\ (Python, the app, the website, PostgreSQL).
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = SPECPATH + "/.."
datas = [
    (ROOT + "/backend/alembic.ini", "."),
    (ROOT + "/backend/migrations", "migrations"),  # the database changes, read as files by Alembic
    (ROOT + "/frontend/dist", "website"),           # the built website
    (ROOT + "/build/pgsql", "pgsql"),               # PostgreSQL's programs (initdb, postgres, pg_dump...)
] + collect_data_files("tzdata")                  # time zones: Windows has none for Python

hidden = (collect_submodules("app") + collect_submodules("uvicorn")
          + collect_submodules("sklearn") + collect_submodules("scipy") + ["psycopg_binary"])

a = Analysis(
    [SPECPATH + "/autostock_main.py"],
    pathex=[ROOT + "/backend"],
    datas=datas,
    hiddenimports=hidden,
    excludes=["pytest", "tkinter", "matplotlib", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AutoStock", icon=SPECPATH + "/autostock.ico",
          console=False, upx=False)
COLLECT(exe, a.binaries, a.datas, name="AutoStock", upx=False)
