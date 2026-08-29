from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, require_platform_permission
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.global_template_service import GlobalTemplateService
from app.services.template_contract import TemplateContract
from app.services.template_import_service import TemplateImportService

router = APIRouter()

DEVELOPER_KIT_DIR = Path(__file__).resolve().parents[4] / "resources" / "avb-template-kit"
DeveloperKitArtifact = Literal[
    "ai-standard",
    "sdk-guide",
    "experience-contract",
    "bindings",
    "theme-tokens",
    "migration-guide",
    "example-package",
    "avb-package",
]
DEVELOPER_KIT_ARTIFACTS: dict[str, tuple[str, str, str]] = {
    "ai-standard": ("ARGWS_Visual_Builder_2.4.0_TEMPLATE_AI_STANDARD.md", "Padrão mestre para IA", "text/markdown"),
    "sdk-guide": ("TEMPLATE_RUNTIME_SDK_V1.md", "Template Runtime SDK v1", "text/markdown"),
    "experience-contract": ("EXPERIENCE_CONTRACT_V2.md", "Experience Contract v2", "text/markdown"),
    "bindings": ("BINDINGS_V1.md", "Bindings v1", "text/markdown"),
    "theme-tokens": ("THEME_TOKENS_V1.md", "Theme Tokens v1", "text/markdown"),
    "migration-guide": ("MIGRATION_V1_TO_V2.md", "Migração v1 → v2", "text/markdown"),
    "example-package": ("ARGWS_Experience_Template_v2_EXEMPLO-ENRIQUECIDO.zip", "Experience Package v2 — exemplo enriquecido", "application/zip"),
    "avb-package": ("argws-visual-builder-2.4.0.tgz", "ARGWS Visual Builder 2.4.0 — pacote NPM", "application/gzip"),
}


def _developer_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, (filename, label, media_type) in DEVELOPER_KIT_ARTIFACTS.items():
        path = DEVELOPER_KIT_DIR / filename
        if not path.is_file():
            continue
        rows.append(
            {
                "key": key,
                "label": label,
                "filename": filename,
                "media_type": media_type,
                "size_bytes": path.stat().st_size,
            }
        )
    return rows


class TemplateCreate(BaseModel):
    surface: Literal["LANDING", "BOOKING"]
    key: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    segment: str | None = Field(default=None, max_length=80)
    status: Literal["DRAFT", "PUBLISHED", "INACTIVE"] = "DRAFT"
    scope: Literal["GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"] = "INTERNAL"
    default_for_new_tenants: bool = False
    exclusive_tenant_id: str | None = None
    selected_tenant_ids: list[str] = Field(default_factory=list)
    content: dict[str, Any] | None = None
    changelog: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    segment: str | None = Field(default=None, max_length=80)
    status: Literal["DRAFT", "PUBLISHED", "INACTIVE"] | None = None
    scope: Literal["GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"] | None = None
    default_for_new_tenants: bool | None = None
    exclusive_tenant_id: str | None = None
    selected_tenant_ids: list[str] | None = None


class TemplateVersionCreate(BaseModel):
    content: dict[str, Any]
    changelog: str | None = None
    publish: bool = False


class TemplateDuplicate(BaseModel):
    key: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=180)


class TemplateBundleValidation(BaseModel):
    bundle: dict[str, Any]


class TemplateBundleImport(BaseModel):
    bundle: dict[str, Any]
    scope_override: Literal["GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"] | None = None
    exclusive_tenant_id: str | None = None
    selected_tenant_ids: list[str] | None = None
    publish: bool = False
    update_existing: bool = True


@router.get("")
async def list_global_templates(
    surface: Literal["LANDING", "BOOKING"] | None = Query(default=None),
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).list(
            surface=surface,
            include_internal=True,
        )
    )


@router.get("/contract")
async def template_contract(
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    return success(TemplateContract.descriptor())


@router.post("/import/validate")
async def validate_template_bundle(
    payload: TemplateBundleValidation,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    return success(TemplateContract.validate_package(payload.bundle))


@router.post("/import")
async def import_template_bundle(
    payload: TemplateBundleImport,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await TemplateImportService(session).import_bundle(
            payload.bundle,
            actor=principal.email,
            scope_override=payload.scope_override,
            exclusive_tenant_id=payload.exclusive_tenant_id,
            selected_tenant_ids=payload.selected_tenant_ids,
            publish=payload.publish,
            update_existing=payload.update_existing,
        )
    )


@router.get("/available/{tenant_id}")
async def available_templates_for_tenant(
    tenant_id: str,
    surface: Literal["LANDING", "BOOKING"] | None = Query(default=None),
    _: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).list(
            surface=surface,
            tenant_id=tenant_id,
        )
    )


@router.post("")
async def create_global_template(
    payload: TemplateCreate,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    if payload.content is not None:
        TemplateContract.ensure_content(payload.surface, payload.content, strict=True)
    return success(
        await GlobalTemplateService(session).create(
            payload.model_dump(),
            actor=principal.email,
        )
    )


@router.get("/developer-kit")
async def developer_kit(
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    standard_path = DEVELOPER_KIT_DIR / "ARGWS_Visual_Builder_2.4.0_TEMPLATE_AI_STANDARD.md"
    sdk_path = DEVELOPER_KIT_DIR / "TEMPLATE_RUNTIME_SDK_V1.md"
    return success(
        {
            "version": "2.4.0",
            "runtime_sdk": "Template Runtime SDK v1",
            "experience_contract": "argws-experience-package/v2",
            "bindings_contract": "argws-bindings/v1",
            "theme_contract": "argws-theme-tokens/v1",
            "ai_standard": standard_path.read_text(encoding="utf-8") if standard_path.is_file() else "",
            "sdk_guide": sdk_path.read_text(encoding="utf-8") if sdk_path.is_file() else "",
            "artifacts": _developer_artifacts(),
        }
    )


@router.get("/developer-kit/artifacts/{artifact}")
async def download_developer_kit_artifact(
    artifact: DeveloperKitArtifact,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> FileResponse:
    filename, _label, media_type = DEVELOPER_KIT_ARTIFACTS[artifact]
    path = DEVELOPER_KIT_DIR / filename
    if not path.is_file():
        raise APIError("AVB_DEVELOPER_ARTIFACT_MISSING", "Material do AVB não está disponível nesta instalação.", 404)
    return FileResponse(path, filename=filename, media_type=media_type)


@router.get("/{template_id}")
async def global_template_detail(
    template_id: str,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await GlobalTemplateService(session).get(template_id))


@router.put("/{template_id}")
async def update_global_template(
    template_id: str,
    payload: TemplateUpdate,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).update_metadata(
            template_id,
            payload.model_dump(exclude_unset=True),
            actor=principal.email,
        )
    )


@router.post("/{template_id}/versions")
async def create_global_template_version(
    template_id: str,
    payload: TemplateVersionCreate,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    template = await GlobalTemplateService(session).get(template_id)
    TemplateContract.ensure_content(str(template["surface"]), payload.content, strict=True)
    return success(
        await GlobalTemplateService(session).create_version(
            template_id,
            payload.content,
            changelog=payload.changelog,
            actor=principal.email,
            publish=payload.publish,
        )
    )


@router.post("/{template_id}/versions/{version_number}/publish")
async def publish_global_template_version(
    template_id: str,
    version_number: int,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    current = await GlobalTemplateService(session).content(
        template_id=template_id,
        version_number=version_number,
    )
    TemplateContract.ensure_content(
        str(current["surface"]),
        current["version"]["content"],
        strict=True,
    )
    return success(
        await GlobalTemplateService(session).publish_version(
            template_id,
            version_number,
            actor=principal.email,
        )
    )


@router.get("/{template_id}/versions/{version_number}/content")
async def global_template_version_content(
    template_id: str,
    version_number: int,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    data = await GlobalTemplateService(session).content(
        template_id=template_id,
        version_number=version_number,
    )
    TemplateContract.ensure_content(
        str(data["surface"]),
        data["version"]["content"],
        strict=False,
    )
    return success(data)


@router.post("/{template_id}/duplicate")
async def duplicate_global_template(
    template_id: str,
    payload: TemplateDuplicate = Body(...),
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).duplicate(
            template_id,
            new_key=payload.key,
            new_name=payload.name,
            actor=principal.email,
        )
    )
