"""轻量幂等结构补齐：create_all 只建新表、不会给已有表加列，
这里为历史库补新增列，避免重建卷。仅在列缺失时执行 ALTER。"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_COLUMN_DEFAULTS = {
    "halls": [("absent_strategy", "VARCHAR(16) DEFAULT 'retain'")],
    "seat_plans": [("voided_at", "TIMESTAMP NULL")],
}


def ensure_columns(engine: Engine) -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, columns in _COLUMN_DEFAULTS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in insp.get_columns(table)}
            for name, ddl_type in columns:
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))
