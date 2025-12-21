# File name: main.py
# Created: 12/21/2025 1:18 PM
# Purpose: Simple Gradio web UI MVP for Financial Analysis Forge (Excel upload -> display)
# Notes:
# - Upload an .xlsx/.xls file, reads the first sheet, and displays it in a table
# - Also shows detected sheet names for quick sanity checking
# Used: Yes

import gradio as gr
import pandas as pd


def load_excel(file_obj):
	# file_obj is a gradio UploadedFile-like object with a .name path
	if file_obj is None:
		return pd.DataFrame(), "No file uploaded."

	path = getattr(file_obj, "name", None)
	if not path:
		return pd.DataFrame(), "Could not read uploaded file path."

	try:
		xl = pd.ExcelFile(path)
		sheet_names = xl.sheet_names

		# Read first sheet by default
		df = pd.read_excel(xl, sheet_name=sheet_names[0])

		return df, f"Sheets: {', '.join(sheet_names)}\nShowing: {sheet_names[0]}"
	except Exception as e:
		return pd.DataFrame(), f"Error reading Excel: {e}"


def build_app():
	with gr.Blocks(title="Financial Analysis Forge - MVP") as demo:
		gr.Markdown("# Financial Analysis Forge (MVP)\nUpload an Excel file and preview the first sheet.")

		with gr.Row():
			excel_file = gr.File(label="Upload Excel (.xlsx/.xls)", file_types=[".xlsx", ".xls"])
		status = gr.Textbox(label="Status", interactive=False)
		table = gr.Dataframe(label="Preview", interactive=False, wrap=True)

		excel_file.change(
			fn=load_excel,
			inputs=[excel_file],
			outputs=[table, status],
		)

	return demo


if __name__ == "__main__":
	app = build_app()
	app.launch()
