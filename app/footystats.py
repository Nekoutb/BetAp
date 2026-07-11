import httpx

from .config import Settings


class FootyStatsClient:
    def __init__(self, settings: Settings):
        if not settings.footystats_api_key:
            raise RuntimeError("FOOTYSTATS_API_KEY is not configured")
        self.base_url = settings.footystats_base_url.rstrip("/")
        self.api_key = settings.footystats_api_key

    async def get(self, endpoint: str, **params: object) -> dict:
        # The key is injected only at request time and never logged.
        params["key"] = self.api_key
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()

    async def todays_matches(self, timezone: str = "Europe/London") -> dict:
        return await self.get("/todays-matches", timezone=timezone)

    async def match(self, match_id: int) -> dict:
        return await self.get("/match", match_id=match_id)
