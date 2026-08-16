from sqlalchemy import text

from app.services.auth_service import PlatformAuthService as BasePlatformAuthService


class PlatformAuthService(BasePlatformAuthService):
    async def _permissions(
        self,
        user_id: str,
        is_super_admin: bool = False,
    ) -> tuple[list[str], list[str]]:
        if is_super_admin:
            permission_rows = await self.session.execute(
                text("select key from platform_permissions order by key")
            )
            return list(permission_rows.scalars()), ["super-admin"]

        permission_rows = await self.session.execute(
            text(
                """
                select distinct rp.permission_key
                from platform_role_permissions rp
                join platform_user_roles ur on ur.role_id=rp.role_id
                where ur.user_id=cast(:user_id as uuid)
                order by rp.permission_key
                """
            ),
            {"user_id": user_id},
        )
        role_rows = await self.session.execute(
            text(
                """
                select distinct r.name
                from platform_roles r
                join platform_user_roles ur on ur.role_id=r.id
                where ur.user_id=cast(:user_id as uuid)
                order by r.name
                """
            ),
            {"user_id": user_id},
        )
        return list(permission_rows.scalars()), list(role_rows.scalars())
