from __future__ import annotations
from quart import Blueprint, render_template, request, redirect, url_for
import main.globals.configurator as config 
import main.globals.app_state as state
from main.handlers.income_statement_table import parse_income_statement_tables_from_path
import os, io

bp = Blueprint("home", __name__)


@bp.get("/")
async def index():
    return await render_template(
        "index.html",
        status=state.get_status(),
        excel_path=state.get_excel_path()
    )


@bp.post("/upload")
async def upload_and_parse():
    files = await request.files
    f = files.get("file")

    if f is None:
        state.set_status("No file provided.")
        return await render_template("index.html", status=state.get_status(), excel_path=state.get_excel_path())

    upload_dir = os.path.join(os.getcwd(), "storage", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    save_path = os.path.join(upload_dir, f.filename)
    await f.save(save_path)

    state.clear_all()
    state.set_excel_path(save_path)
    state.set_status(f"Uploaded: {f.filename} | Parsing...")

    try:
        parse_income_statement_tables_from_path(save_path, progress_cb=None)
        state.set_status(f"Uploaded: {f.filename} | Parse complete.")
    except Exception as e:
        state.set_status(f"Parse failed: {e}")

    return redirect(url_for("income_statement.income_statement"))
