from pathlib import Path

from alembic import op
from sqlalchemy import text


def execute_sql_file(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            op.get_bind().execute(text(statement))
