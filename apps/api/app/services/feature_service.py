from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_platform import FeatureFlag


class FeatureService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_enabled(self, key: str, tenant_id: str | None = None, plan_id: str | None = None) -> bool:
        flag = await self.session.get(FeatureFlag, key)
        if flag is None:
            return False
        rules: dict[str, Any] = flag.rules if isinstance(flag.rules, dict) else {}
        denied_tenants = {str(value) for value in rules.get("deny_tenants", []) if value}
        allowed_tenants = {str(value) for value in rules.get("allow_tenants", []) if value}
        allowed_plans = {str(value) for value in rules.get("allow_plans", []) if value}
        if tenant_id and tenant_id in denied_tenants:
            return False
        if allowed_tenants and (not tenant_id or tenant_id not in allowed_tenants):
            return False
        if allowed_plans and (not plan_id or plan_id not in allowed_plans):
            return False
        return bool(flag.enabled)

    async def list_flags(self) -> list[dict[str, Any]]:
        flags = (await self.session.execute(select(FeatureFlag).order_by(FeatureFlag.key))).scalars().all()
        return [{"key": flag.key, "enabled": flag.enabled, "rules": flag.rules} for flag in flags]
