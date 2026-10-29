"""In production the server also serves the built website (frontend/dist, copied into the image),
so everything runs on one port. Every address that isn't /api or a file gets index.html: the
website's own router then shows the right page (or its "Page not found")."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def serve_website(app: FastAPI, folder: Path) -> None:
    index = folder / "index.html"
    # Scripts, styles and fonts. Their names change with their content, so an update is never mixed with old files.
    app.mount("/assets", StaticFiles(directory=folder / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def website(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404)
        file = (folder / path).resolve()
        if path and file.is_file() and file.is_relative_to(folder.resolve()):
            return FileResponse(file)
        # Never kept by the browser: after an update everyone gets the new website at once.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
