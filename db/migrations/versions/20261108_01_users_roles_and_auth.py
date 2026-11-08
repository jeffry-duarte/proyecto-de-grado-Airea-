"""Add role relationships and password scheme tracking.

Revision ID: 20261108_01
Revises:
Create Date: 2026-11-08
Author: Jeffry Duarte
"""

from alembic import op
import sqlalchemy as sa


revision = "20261108_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "roles" not in table_names:
        op.create_table(
            "roles",
            sa.Column("id", sa.String(length=80), primary_key=True),
            sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        )
    if "users" not in table_names:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.UniqueConstraint("email", name="users_email_key"),
            sa.Column("password_salt", sa.Text(), nullable=False, server_default=""),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column(
                "password_scheme",
                sa.String(length=16),
                nullable=False,
                server_default="bcrypt",
            ),
            sa.Column("locality", sa.String(length=100), nullable=False),
            sa.Column(
                "favorite_station_id", sa.String(length=80), nullable=False
            ),
            sa.Column("health_profile", sa.String(length=32), nullable=False),
            sa.Column(
                "notifications_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "role",
                sa.String(length=80),
                nullable=False,
                server_default="citizen",
            ),
            sa.Column(
                "role_id",
                sa.String(length=80),
                sa.ForeignKey("roles.id"),
                nullable=False,
                server_default="citizen",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    columns = {column["name"]: column for column in inspector.get_columns("users")}
    if "password_scheme" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "password_scheme",
                sa.String(length=16),
                nullable=False,
                server_default="scrypt",
            ),
        )
    if "role_id" not in columns:
        role_id_column = sa.Column(
            "role_id",
            sa.String(length=80),
            nullable=True,
        )
        if bind.dialect.name != "sqlite":
            role_id_column.append_foreign_key(sa.ForeignKey("roles.id"))
        op.add_column("users", role_id_column)

    role_names = {"citizen", "admin"}
    if "role" in columns:
        role_names.update(
            str(value)
            for value, in bind.execute(
                sa.text("SELECT DISTINCT role FROM users WHERE role IS NOT NULL")
            )
            if str(value)
        )
    elif "role_id" in columns:
        role_names.update(
            str(value)
            for value, in bind.execute(
                sa.text("SELECT DISTINCT role_id FROM users WHERE role_id IS NOT NULL")
            )
            if str(value)
        )

    for role_name in role_names:
        bind.execute(
            sa.text(
                "INSERT INTO roles (id, name) VALUES (:id, :name) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": role_name, "name": role_name},
        )

    if "role" in columns:
        bind.execute(sa.text("""
            UPDATE users
            SET role_id = CASE
                WHEN role IS NULL OR role = '' THEN 'citizen'
                ELSE role
            END
        """))
    else:
        bind.execute(
            sa.text("UPDATE users SET role_id = 'citizen' WHERE role_id IS NULL")
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "users_role_id_idx" not in indexes:
        op.create_index("users_role_id_idx", "users", ["role_id"])

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "users",
            "role_id",
            existing_type=sa.String(length=80),
            nullable=False,
        )
        op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE roles ENABLE ROW LEVEL SECURITY")
    elif bind.dialect.name == "sqlite" and columns.get("role_id", {}).get(
        "nullable", True
    ):
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS users_role_id_required_insert
            BEFORE INSERT ON users
            WHEN NEW.role_id IS NULL
                OR NOT EXISTS (SELECT 1 FROM roles WHERE roles.id = NEW.role_id)
            BEGIN SELECT RAISE(ABORT, 'users.role_id must reference a role'); END
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS users_role_id_required_update
            BEFORE UPDATE OF role_id ON users
            WHEN NEW.role_id IS NULL
                OR NOT EXISTS (SELECT 1 FROM roles WHERE roles.id = NEW.role_id)
            BEGIN SELECT RAISE(ABORT, 'users.role_id must reference a role'); END
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS roles_restrict_delete
            BEFORE DELETE ON roles
            WHEN EXISTS (SELECT 1 FROM users WHERE users.role_id = OLD.id)
            BEGIN SELECT RAISE(ABORT, 'role is still assigned to users'); END
        """)


def downgrade() -> None:
    raise RuntimeError(
        "La migración no se puede revertir de forma segura: el nuevo formato "
        "Bcrypt no puede convertirse de nuevo a hashes Scrypt."
    )
