"""All tables. Importing this package registers them with Alembic."""

from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.import_mapping import ImportMapping
from app.models.login_failure import LoginFailure
from app.models.organization import Organization
from app.models.part import Part
from app.models.part_equivalent import EQUIVALENT_SOURCES, EquivalentSource, PartEquivalent
from app.models.sale_line import SaleLine
from app.models.stock_level import StockLevel
from app.models.supplier import Supplier
from app.models.synonym_group import SynonymGroup
from app.models.user import ROLES, Role, User
from app.models.user_session import UserSession

__all__ = [
    "EQUIVALENT_SOURCES",
    "ROLES",
    "AuditLog",
    "Branch",
    "EquivalentSource",
    "ImportMapping",
    "LoginFailure",
    "Organization",
    "Part",
    "PartEquivalent",
    "Role",
    "SaleLine",
    "StockLevel",
    "Supplier",
    "SynonymGroup",
    "User",
    "UserSession",
]
