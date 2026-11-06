from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import app.database.models  # noqa: F401  register every table on Base.metadata
from app.config import settings
from app.database.session import Base

config = context.config
if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

# Tests pass their own URL via config attributes; everything else uses settings.
url = config.attributes.get("database_url", settings.database_url)

with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
