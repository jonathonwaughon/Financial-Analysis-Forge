# File name: logic_engine.py
# Created: 1/23/2026 7:16 PM
# Purpose: Encapsulated logic for the app
# Notes:
# - Global registry for extracted tables + misc app data
# - Supports shallow lookup + optional deep recursive lookup
# Used: Yes

from main.core.global_state import GlobalState
from main.handlers.income_statement import parse_income_statement_tables_from_path

class Engine():

    def __init__(self):
        self._created_timestamp = "hi"
        state = GlobalState()
        self.GlobalState = state



    def get_state(self):
        return self.GlobalState


    def update_excel(self, path):
        self.GlobalState.excel_path = path


    def parse_excel(self):
        if self.GlobalState.excel_path == None:
            print("path is none?")
            return
        income_statement = parse_income_statement_tables_from_path(self.GlobalState.excel_path)
        self.GlobalState.insert_data("income_statement", income_statement)

LogicEngine = Engine()