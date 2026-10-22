"""Audit log — every role. The backend scopes results by role:
Admin sees everyone; HR sees HR/Manager/Employee; Manager sees
Manager/HR/Employee; Employee sees only its own. No client-side
filtering is needed here — just display whatever comes back."""
from controllers.api_client import api_client


def list_audit_log(limit: int = 200) -> list:
    return api_client.get("/api/audit-log", params={"limit": limit}) or []
