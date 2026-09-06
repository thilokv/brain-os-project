"""add password credentials to users

Phase 2B.4: authentication. Adds the credential column that
6d389c38a0c8's own docstring explicitly deferred ("No password/
credential column is added here... an explicitly separate later
milestone") -- this is that milestone.

password_hash stores a bcrypt hash only, never a plaintext or
reversibly-encrypted password (see app/services/auth_service.py).
NOT NULL with no DEFAULT: there is no pre-launch data in this table,
so every existing/future row is required to have a real credential
from the moment this migration applies -- no placeholder value is
introduced that could ever be mistaken for a valid hash or silently
allow a passwordless account through.

Written as hand-executed raw SQL (op.execute), consistent with every
other migration in this chain -- no SQLAlchemy ORM.

Revision ID: 01401ec64495
Revises: 6d389c38a0c8
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01401ec64495"
down_revision: Union[str, Sequence[str], None] = "6d389c38a0c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN password_hash")
