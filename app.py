from __future__ import annotations

from rich.console import Console
from quart import Quart
import main.core.configurator as config

# Blueprint imports
from main.app.web.home import bp as home_bp
from main.app.web.income_statement import bp as income_statement_bp
from main.app.web.balance_sheet import bp as balance_sheet_bp

# Engine imports
from main.core.logic_engine import LogicEngine

console = Console(color_system="256")
console.print(f"Running version: [cyan]{config.get_config('DO_NOT_MODIFY.version')}[/cyan]")

app = Quart(__name__, template_folder="main/app/templates", static_folder="main/app/static")

app.register_blueprint(home_bp)
app.register_blueprint(income_statement_bp)
app.register_blueprint(balance_sheet_bp)

if __name__ == "__main__":
    console.log(f"Starting web application on port: [red] {config.get_config('app.port')}[/red]")
    app.run(port=config.get_config("app.port"))
