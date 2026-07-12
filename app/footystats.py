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

    async def matches_by_date(self, date: str, timezone: str = "Europe/London") -> list[dict]:
        matches: list[dict] = []
        page = 1
        while True:
            payload = await self.get("/todays-matches", timezone=timezone, date=date, page=page)
            matches.extend(payload.get("data") or [])
            pager = payload.get("pager") or {}
            if page >= int(pager.get("max_page") or 1):
                return matches
            page += 1

    async def match(self, match_id: int) -> dict:
        return await self.get("/match", match_id=match_id)

    async def league_index(self) -> dict[int, dict]:
        payload=await self.get("/league-list",chosen_leagues_only="true")
        index={}
        for league in payload.get("data") or []:
            for season in league.get("season") or []:
                index[int(season["id"])]={"league":league.get("league_name") or league.get("name") or "Unknown competition","country":league.get("country") or "Unknown country","division":league.get("division"),"season":season.get("year")}
        return index
