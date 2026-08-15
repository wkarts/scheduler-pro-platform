class FeatureService:
    async def is_enabled(self, key: str, tenant_id: str | None = None, plan_id: str | None = None) -> bool:
        # Nunca usar if plan == premium espalhado pelo código.
        return key in {"appointments", "landing_pages", "whatsapp"}
