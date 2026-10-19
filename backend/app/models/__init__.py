"""All tables. Importing this package registers them with Alembic."""

from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.demo_true_demand import DemoTrueDemand
from app.models.forecast import Forecast, ForecastRun
from app.models.import_mapping import ImportMapping
from app.models.login_failure import LoginFailure
from app.models.order_suggestion import OrderRun, OrderSuggestion
from app.models.organization import Organization
from app.models.part import Part
from app.models.part_equivalent import EQUIVALENT_SOURCES, EquivalentSource, PartEquivalent
from app.models.sale_line import SaleLine
from app.models.stock_level import StockLevel
from app.models.stock_out import StockOut
from app.models.supplier import Supplier
from app.models.synonym_group import SynonymGroup
from app.models.user import ROLES, Role, User
from app.models.user_session import UserSession

__all__ = [
    "EQUIVALENT_SOURCES",
    "ROLES",
    "AuditLog",
    "Branch",
    "DemoTrueDemand",
    "Forecast",
    "ForecastRun",
    "EquivalentSource",
    "ImportMapping",
    "LoginFailure",
    "OrderRun",
    "OrderSuggestion",
    "Organization",
    "Part",
    "PartEquivalent",
    "Role",
    "SaleLine",
    "StockLevel",
    "StockOut",
    "Supplier",
    "SynonymGroup",
    "User",
    "UserSession",
]
