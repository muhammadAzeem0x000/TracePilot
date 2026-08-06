from collections.abc import Mapping

import httpx


class StorageError(Exception):
    """Raised when Supabase cannot satisfy a persistence operation."""


class SupabaseRestClient:
    """Small async PostgREST client scoped to the operations Day 1 needs."""

    def __init__(self, project_url: str, api_key: str) -> None:
        self._base_url = f"{project_url}/rest/v1"
        self._headers = {
            "apikey": api_key,
            "Accept": "application/json",
        }
        # Legacy service-role keys are JWTs and may be sent as Bearer tokens. Modern
        # `sb_secret_` keys authenticate through `apikey` and are not JWTs.
        if not api_key.startswith("sb_secret_"):
            self._headers["Authorization"] = f"Bearer {api_key}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, object] | None = None,
        prefer_representation: bool = False,
        extra_headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, object]]:
        headers = dict(self._headers)
        if prefer_representation:
            headers["Prefer"] = "return=representation"
        if extra_headers:
            headers.update(extra_headers)

        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip().replace("\n", " ")[:500]
            message = f"Supabase request failed with HTTP {exc.response.status_code}"
            if detail:
                message = f"{message}: {detail}"
            raise StorageError(message) from exc
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise StorageError("Supabase request failed before receiving a response") from exc

        try:
            payload: object = response.json()
        except ValueError as exc:
            raise StorageError("Supabase returned invalid JSON") from exc

        if not isinstance(payload, list):
            raise StorageError("Supabase returned an unexpected response shape")

        records: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise StorageError("Supabase returned an invalid record")
            records.append({str(key): value for key, value in item.items()})
        return records
