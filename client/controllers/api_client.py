"""
Low-level HTTP client for the Meridian Systems FastAPI backend.

This is the single place that knows how to talk to the API: it holds
the auth token, builds headers, and turns HTTP/requests errors into a
single, predictable APIError that every view can catch and show in a
QMessageBox. Nothing above this layer should ever import `requests`
directly.
"""
from __future__ import annotations

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 15  # seconds


class APIError(Exception):
    """Raised for any failed API call (network problem or HTTP 4xx/5xx)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __str__(self) -> str:
        return self.message


class APIClient:
    """
    Thin wrapper around `requests` that:
      - keeps the JWT and attaches it to every request
      - keeps the small bits of session state the UI needs (role, name, ...)
      - raises APIError with a clean, human-readable message on failure
    A single instance (`api_client`, below) is shared across the whole app.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None

        # Session info populated after a successful login (see auth_controller).
        self.role: str | None = None
        self.full_name: str | None = None
        self.email: str | None = None
        self.user_id: int | None = None
        self.must_reset_password: bool = False
        self.two_fa_enabled: bool = False

    # ---- session helpers -------------------------------------------------
    def is_authenticated(self) -> bool:
        return bool(self.token)

    def clear_session(self) -> None:
        self.token = None
        self.role = None
        self.full_name = None
        self.email = None
        self.user_id = None
        self.must_reset_password = False
        self.two_fa_enabled = False

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    # ---- core request handling --------------------------------------------
    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, json=None, params=None):
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                json=json,
                params=params,
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.exceptions.ConnectionError:
            raise APIError(
                f"Could not connect to the server at {self.base_url}.\n"
                "Make sure the backend is running (uvicorn app.main:app --port 8000)."
            )
        except requests.exceptions.Timeout:
            raise APIError("The request timed out. Please try again.")
        except requests.exceptions.RequestException as exc:  # pragma: no cover
            raise APIError(f"Network error: {exc}")

        if response.status_code >= 400:
            raise APIError(self._extract_error(response), response.status_code)

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _extract_error(response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text or f"Request failed with status {response.status_code}."

        detail = data.get("detail") if isinstance(data, dict) else None

        if isinstance(detail, list):
            # FastAPI/Pydantic validation error format.
            messages = []
            for item in detail:
                if isinstance(item, dict):
                    loc = ".".join(str(part) for part in item.get("loc", []) if part != "body")
                    msg = item.get("msg", "Invalid value.")
                    messages.append(f"{loc}: {msg}" if loc else msg)
                else:
                    messages.append(str(item))
            return "\n".join(messages) if messages else "Validation error."

        if isinstance(detail, str):
            return detail

        return f"Request failed with status {response.status_code}."

    # ---- verbs -------------------------------------------------------------
    def get(self, path: str, params: dict | None = None):
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None):
        return self._request("POST", path, json=json)

    def patch(self, path: str, json: dict | None = None):
        return self._request("PATCH", path, json=json)

    def put(self, path: str, json: dict | None = None):
        return self._request("PUT", path, json=json)

    def delete(self, path: str):
        return self._request("DELETE", path)


# Single shared instance used by every controller/view in the app.
api_client = APIClient()
