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

def vendored_scipy() -> list[str]:
    """SciPy's vendored helpers (scipy/_external) are loaded by name at run time, so PyInstaller's
    search misses some. List every file there, except the parts for other libraries (CuPy, Dask, PyTorch)."""
    import os

    import scipy

    base = os.path.dirname(scipy.__file__)
    found = []
    for folder, _, files in os.walk(os.path.join(base, "_external")):
        for name in files:
            if not name.endswith(".py"):
                continue
            module = os.path.relpath(os.path.join(folder, name), os.path.dirname(base))[:-3].replace(os.sep, ".")
            module = module.removesuffix(".__init__")
            if not any(f".{skip}" in module for skip in ("cupy", "dask", "torch", "testing")):
                found.append(module)
    return found


hidden = (collect_submodules("app") + collect_submodules("uvicorn")
          + collect_submodules("sklearn") + collect_submodules("scipy") + vendored_scipy() + ["psycopg_binary"])

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
