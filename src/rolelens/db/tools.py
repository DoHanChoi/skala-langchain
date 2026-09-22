"""LangChain tools that expose only the controlled database repository."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from rolelens.db.repository import AnalyticsRepository


def create_database_tools(repository: AnalyticsRepository) -> dict[str, BaseTool]:
    @tool
    def list_tables() -> list[dict[str, str]]:
        """List the allowlisted analytics tables with business descriptions."""

        return repository.list_tables()

    @tool
    def inspect_schema(table_names: list[str]) -> list[dict]:
        """Inspect columns, keys, and descriptions for allowlisted table names."""

        return repository.inspect_schema(table_names)

    @tool
    def execute_readonly_sql(sql: str, attempts: int = 1) -> dict:
        """Validate and execute one PostgreSQL SELECT against allowlisted analytics tables."""

        return repository.execute_readonly_sql(sql, attempts=attempts).model_dump(mode="python")

    return {
        "list_tables": list_tables,
        "inspect_schema": inspect_schema,
        "execute_readonly_sql": execute_readonly_sql,
    }
