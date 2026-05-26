"""
backend/app/models/base.py
--------------------------
Single declarative Base shared across all ORM models.
Importing from individual model files each created their own Base,
which breaks Alembic autogenerate. All models must import from here.
"""
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy import MetaData

# Consistent constraint naming convention for Alembic migrations
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base."""
    metadata = MetaData(naming_convention=convention)