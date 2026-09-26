"""Copy the local MySQL database into the configured Supabase PostgreSQL database."""

import os
from collections import OrderedDict

import pymysql
from sqlalchemy import create_engine, text

from app.config import Config
from app.models import db


TABLE_ORDER = [
    "users",
    "data_sources",
    "organizations",
    "raw_data",
    "prospects",
    "events",
    "event_participants",
    "duplicate_candidates",
    "campaigns",
    "campaign_targets",
    "activity_logs",
    "cron_jobs",
    "ai_agent_configs",
    "discovery_sources",
    "market_analyses",
    "reports",
]


def source_connection():
    return pymysql.connect(
        host=os.getenv("SOURCE_DB_HOST", "localhost"),
        port=int(os.getenv("SOURCE_DB_PORT", "3306")),
        user=os.getenv("SOURCE_DB_USER", "root"),
        password=os.getenv("SOURCE_DB_PASSWORD", ""),
        database=os.getenv("SOURCE_DB_NAME", "market_intelligence"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def ordered_tables(source_cursor):
    source_cursor.execute("SHOW TABLES")
    key = source_cursor.description[0][0]
    source_tables = [row[key] for row in source_cursor.fetchall()]
    return [table for table in TABLE_ORDER if table in source_tables] + [
        table for table in source_tables if table not in TABLE_ORDER
    ]


def copy_table(source_cursor, target_connection, table_name):
    source_cursor.execute(f"SELECT * FROM `{table_name}`")
    rows = source_cursor.fetchall()
    target_table = db.metadata.tables[table_name]
    target_columns = {column.name for column in target_table.columns}
    rows = [
        {column: value for column, value in row.items() if column in target_columns}
        for row in rows
    ]

    for start in range(0, len(rows), 500):
        target_connection.execute(target_table.insert(), rows[start : start + 500])
    return len(rows)


def reset_sequences(target_connection):
    for table in db.metadata.sorted_tables:
        primary_key = next(iter(table.primary_key.columns), None)
        if primary_key is None or not isinstance(primary_key.type.python_type, type):
            continue
        if primary_key.name != "id":
            continue
        sequence_name = f"{table.name}_id_seq"
        target_connection.execute(
            text(
                "SELECT setval(:sequence_name, "
                "COALESCE((SELECT MAX(id) FROM \"" + table.name + "\"), 1), "
                "(SELECT COUNT(*) > 0 FROM \"" + table.name + "\"))"
            ),
            {"sequence_name": sequence_name},
        )


def main():
    target_engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
    db.metadata.create_all(target_engine)

    with source_connection() as source, target_engine.begin() as target:
        source_cursor = source.cursor()
        tables = ordered_tables(source_cursor)
        target.execute(text("TRUNCATE TABLE " + ", ".join(f'\"{table}\"' for table in tables) + " CASCADE"))

        counts = OrderedDict()
        for table in tables:
            counts[table] = copy_table(source_cursor, target, table)
            print(f"{table}: {counts[table]}")

        reset_sequences(target)
        print("Migration completed")


if __name__ == "__main__":
    main()