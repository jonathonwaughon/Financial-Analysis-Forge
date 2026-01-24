from __future__ import annotations

from quart import Blueprint, render_template, request, redirect, url_for
from main.core.logic_engine import LogicEngine
from main.handlers.income_statement import parse_income_statement_tables_from_path

import os


bp = Blueprint("home", __name__)





def _list_excel_files(upload_dir: str) -> list[str]:
    try:
        names = os.listdir(upload_dir)
    except FileNotFoundError:
        return []

    excel_files: list[str] = []
    for name in names:
        lower = name.lower()
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            full_path = os.path.join(upload_dir, name)
            if os.path.isfile(full_path):
                excel_files.append(name)

    excel_files.sort(key=str.lower)
    return excel_files
    
def update_excel_path(new_path: str) -> None:
    LogicEngine.update_excel(new_path)
    LogicEngine.parse_excel()


@bp.get("/")
async def index():
    path = LogicEngine.get_state().get("excel_path")
    upload_dir = os.path.join(os.getcwd(), "storage", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    print(upload_dir)
    files = _list_excel_files(upload_dir)
    print(files)
    if path == None:
        if files:
            path = os.path.join(upload_dir, files[0])
            update_excel_path(path)
        

    return await render_template(
        "index.html",
        status="Running",
        excel_path=path,
        excel_files=files,
        selected_file=path,
    )


@bp.post("/upload")
async def upload_and_parse():
    upload_dir = _get_upload_dir()

    form = await request.form
    files = await request.files

    selected_existing = (form.get("excel_select") or "").strip()
    uploaded = files.get("file")

    save_path = ""

    # Case 1: user uploaded a new file
    if uploaded is not None and uploaded.filename:
        filename = os.path.basename(uploaded.filename)

        if not filename.lower().endswith((".xlsx", ".xls")):
            State.set_status("Invalid file type. Please upload a .xlsx or .xls file.")
            return redirect(url_for("home.index"))

        save_path = os.path.join(upload_dir, filename)
        await uploaded.save(save_path)

    # Case 2: user chose an existing file from dropdown (no upload)
    elif selected_existing:
        candidate = os.path.join(upload_dir, os.path.basename(selected_existing))
        if not os.path.isfile(candidate):
            State.set_status("Selected file not found.")
            return redirect(url_for("home.index"))
        save_path = candidate

    else:
        State.set_status("No file provided or selected.")
        return redirect(url_for("home.index"))

    State.clear_all()
    State.set_excel_path(save_path)
    State.set_status(f"Using: {os.path.basename(save_path)} | Parsing...")

    try:
        parse_income_statement_tables_from_path(save_path, progress_cb=None)
        State.set_status(f"Using: {os.path.basename(save_path)} | Parse complete.")
    except Exception as e:
        State.set_status(f"Parse failed: {e}")

    return redirect(url_for("income_statement.income_statement"))
