#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent.parent
PACKAGE_VERSION = json.loads((PACKAGE_ROOT / 'package.json').read_text(encoding='utf-8'))['version']

OLD_RUNTIME_FILES = [
    Path('apps/web/src/TenantPublicPageEditor.vue'),
    Path('apps/web/src/TenantPublicPageEditorV2.vue'),
    Path('apps/web/src/PublicLandingRenderer.vue'),
    Path('apps/web/src/tenantEditorMobileHotfix.css'),
]
BACKEND_SERVICE = Path('apps/api/app/services/landing_service.py')
BACKEND_ROUTES = Path('apps/api/app/api/v1/routes/landing_pages.py')


def fail(message: str) -> None:
    raise SystemExit(f'ERRO: {message}')


def read(path: Path) -> str:
    if not path.exists():
        fail(f'Arquivo esperado não encontrado: {path}')
    return path.read_text(encoding='utf-8')


def backup(repo: Path, paths: list[Path]) -> Path:
    root = repo / '.argws-visual-builder-backup' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for path in paths:
        if not path.exists():
            continue
        target = root / path.relative_to(repo)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return root


def update_json(path: Path, callback) -> None:
    data = json.loads(read(path))
    callback(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def install_package(repo: Path) -> None:
    dest = repo / 'packages' / 'visual-builder'
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for item in ['src', 'styles', 'assets']:
        shutil.copytree(PACKAGE_ROOT / item, dest / item)
    for item in ['package.json', 'LICENSE', 'VERSION']:
        shutil.copy2(PACKAGE_ROOT / item, dest / item)


def patch_root_package(repo: Path) -> None:
    path = repo / 'package.json'

    def mutate(data: dict) -> None:
        workspaces = data.setdefault('workspaces', [])
        if 'packages/visual-builder' not in workspaces:
            workspaces.append('packages/visual-builder')

    update_json(path, mutate)


def patch_web_package(repo: Path) -> None:
    path = repo / 'apps' / 'web' / 'package.json'

    def mutate(data: dict) -> None:
        data.setdefault('dependencies', {})['@argws/visual-builder'] = PACKAGE_VERSION

    update_json(path, mutate)


def patch_app(repo: Path) -> None:
    path = repo / 'apps' / 'web' / 'src' / 'App.vue'
    source = read(path)

    source = re.sub(r"^import TenantPublicPageEditorV2 from './TenantPublicPageEditorV2\.vue'\s*\n", '', source, flags=re.M)
    source = re.sub(r"^import TenantPublicPageEditor from './TenantPublicPageEditor\.vue'\s*\n", '', source, flags=re.M)
    source = re.sub(r"^import './tenantEditorMobileHotfix\.css'\s*\n", '', source, flags=re.M)
    source = re.sub(r"^const visualBuilderEnabled = .*?\n", '', source, flags=re.M)

    if "import TenantVisualPageBuilder from './TenantVisualPageBuilder.vue'" not in source:
        anchors = [
            "import TenantPwaInstallSurface from './TenantPwaInstallSurface.vue'",
            "import TenantWorkspaceCoordinator from './TenantWorkspaceCoordinator.vue'",
        ]
        for anchor in anchors:
            if anchor in source:
                source = source.replace(anchor, "import TenantVisualPageBuilder from './TenantVisualPageBuilder.vue'\n" + anchor, 1)
                break
        else:
            fail('App.vue divergiu: não foi possível localizar âncora segura para importar TenantVisualPageBuilder.')

    source = re.sub(
        r'\s*<TenantVisualPageBuilder\s+v-if="visualBuilderEnabled"\s*/>\s*\n\s*<TenantPublicPageEditorV2\s+v-else\s*/>',
        '\n      <TenantVisualPageBuilder />',
        source,
    )
    source = re.sub(r'\s*<TenantPublicPageEditorV2\s*/>', '\n      <TenantVisualPageBuilder />', source)
    source = re.sub(r'\s*<TenantPublicPageEditor\s*/>', '\n      <TenantVisualPageBuilder />', source)

    lines = source.splitlines()
    seen_component = False
    cleaned = []
    for line in lines:
        if '<TenantVisualPageBuilder' in line:
            if seen_component:
                continue
            seen_component = True
        cleaned.append(line)
    source = '\n'.join(cleaned) + ('\n' if source.endswith('\n') else '')

    if '<TenantVisualPageBuilder' not in source:
        marker = '      <TenantConfigurationCenter />'
        if marker not in source:
            fail('App.vue divergiu: ponto de montagem do editor não localizado.')
        source = source.replace(marker, marker + '\n      <TenantVisualPageBuilder />', 1)

    path.write_text(source, encoding='utf-8')


def patch_public_site(repo: Path) -> None:
    path = repo / 'apps' / 'web' / 'src' / 'PublicSitePage.vue'
    source = read(path)

    source = re.sub(r"^import PublicLandingRenderer from './PublicLandingRenderer\.vue'\s*\n", '', source, flags=re.M)
    if "import PublicVisualLandingRenderer from './PublicVisualLandingRenderer.vue'" not in source:
        anchor = "import PublicBookingWidget from './PublicBookingWidget.vue'"
        if anchor not in source:
            fail('PublicSitePage.vue divergiu: âncora PublicBookingWidget não localizada.')
        source = source.replace(anchor, anchor + "\nimport PublicVisualLandingRenderer from './PublicVisualLandingRenderer.vue'", 1)

    old_type = 'type BlockPageContent={version:number;global_styles?:Record<string,unknown>;seo?:Record<string,unknown>;blocks?:PageBlock[]}'
    new_type = 'type BlockPageContent={version:number;global_styles?:Record<string,unknown>;seo?:Record<string,unknown>;blocks?:PageBlock[];builder?:{schema?:string}}'
    if old_type in source:
        source = source.replace(old_type, new_type, 1)

    source = re.sub(r"^function visualBuilderContent\(value:BlockPageContent\):boolean\{.*?\}\s*\n", '', source, flags=re.M)
    source = re.sub(
        r'<component\s+:is="visualBuilderContent\(blockContent\(landing\.content\)\)\?PublicVisualLandingRenderer:PublicLandingRenderer"([^>]*)>',
        r'<PublicVisualLandingRenderer\1>',
        source,
    )
    source = source.replace('</component>', '</PublicVisualLandingRenderer>')
    source = source.replace(
        '<PublicLandingRenderer v-else :content="blockContent(landing.content)" :services="catalog?.services||[]" :professionals="catalog?.professionals||[]" :template-key="landing.template_key">',
        '<PublicVisualLandingRenderer v-else :content="blockContent(landing.content)" :services="catalog?.services||[]" :professionals="catalog?.professionals||[]">',
    )
    source = source.replace('</PublicLandingRenderer>', '</PublicVisualLandingRenderer>')
    source = source.replace(' :template-key="landing.template_key"', '')

    if '<PublicVisualLandingRenderer v-else' not in source:
        fail('PublicSitePage.vue divergiu: renderer da Landing Page não pôde ser convertido para New-Only.')

    path.write_text(source, encoding='utf-8')


def patch_backend_service(repo: Path) -> None:
    path = repo / BACKEND_SERVICE
    source = read(path)

    if 'label=f"Publicação da versão {version.version_number}"' not in source:
        old = """        page.status = LandingPageStatus.published.value
        page.current_version_id = version.id
        page.draft_version_id = version.id
        await self.session.commit()
        return {
            \"id\": str(page.id),
            \"status\": page.status,
            \"current_version_id\": str(page.current_version_id),
            \"version_number\": version.version_number,
        }
"""
        new = """        previous_published_id = page.current_version_id
        if previous_published_id and str(previous_published_id) != str(version.id):
            previous_published = (
                await self.session.execute(
                    select(LandingPageVersion).where(
                        LandingPageVersion.id == previous_published_id,
                        LandingPageVersion.landing_page_id == page.id,
                    )
                )
            ).scalar_one_or_none()
            if previous_published is not None and not str(previous_published.label or \"\").startswith(
                (\"Publicação da versão \", \"Publicação anterior preservada da versão \", \"Rollback de emergência para versão \", \"Página em branco — emergência\")
            ):
                await self._create_version(
                    page,
                    deepcopy(previous_published.content),
                    label=f\"Publicação anterior preservada da versão {previous_published.version_number}\",
                    source_version_id=str(previous_published.id),
                )

        published_snapshot = await self._create_version(
            page,
            deepcopy(version.content),
            label=f\"Publicação da versão {version.version_number}\",
            source_version_id=str(version.id),
        )
        page.status = LandingPageStatus.published.value
        page.current_version_id = published_snapshot.id
        page.draft_version_id = published_snapshot.id
        await self.session.commit()
        return {
            \"id\": str(page.id),
            \"status\": page.status,
            \"current_version_id\": str(page.current_version_id),
            \"version_number\": published_snapshot.version_number,
            \"source_version_id\": str(version.id),
        }
"""
        if old not in source:
            fail('landing_service.py divergiu: bloco publish não localizado para snapshot seguro.')
        source = source.replace(old, new, 1)

    if 'async def emergency_rollback(' not in source:
        anchor = '    async def duplicate(\n'
        if anchor not in source:
            fail('landing_service.py divergiu: ponto para operações de emergência não localizado.')
        methods = '''    async def emergency_rollback(
        self,
        slug: str,
        *,
        created_by: str | None = None,
    ) -> dict[str, object]:
        # Publica novamente a última versão segura anterior à publicação atual.
        await self._lock_page(slug)
        page = await self._page(slug)
        if page is None or not page.current_version_id:
            raise APIError(
                "LANDING_PUBLISHED_VERSION_NOT_FOUND",
                "Não existe publicação para desfazer.",
                409,
            )

        current = (
            await self.session.execute(
                select(LandingPageVersion).where(
                    LandingPageVersion.id == page.current_version_id,
                    LandingPageVersion.landing_page_id == page.id,
                )
            )
        ).scalar_one_or_none()
        if current is None:
            raise APIError(
                "LANDING_PUBLISHED_VERSION_NOT_FOUND",
                "A versão publicada atual não foi encontrada.",
                409,
            )

        rows = (
            await self.session.execute(
                select(LandingPageVersion)
                .where(
                    LandingPageVersion.landing_page_id == page.id,
                    LandingPageVersion.version_number < current.version_number,
                )
                .order_by(desc(LandingPageVersion.version_number))
                .limit(200)
            )
        ).scalars().all()
        if not rows:
            raise APIError(
                "LANDING_ROLLBACK_NOT_AVAILABLE",
                "Não existe uma versão anterior para restaurar.",
                409,
            )

        publication_prefixes = (
            "Publicação da versão ",
            "Publicação anterior preservada da versão ",
            "Rollback de emergência para versão ",
            "Página em branco — emergência",
        )
        source = next(
            (
                item
                for item in rows
                if str(item.label or "").startswith(publication_prefixes)
            ),
            rows[0],
        )
        restored = await self._create_version(
            page,
            deepcopy(source.content),
            created_by=created_by,
            label=f"Rollback de emergência para versão {source.version_number}",
            source_version_id=str(source.id),
        )
        page.status = LandingPageStatus.published.value
        page.current_version_id = restored.id
        page.draft_version_id = restored.id
        await self.session.commit()
        return {
            "id": str(page.id),
            "status": page.status,
            "current_version_id": str(restored.id),
            "version_number": restored.version_number,
            "restored_from_version_id": str(source.id),
            "restored_from_version_number": source.version_number,
        }

    async def emergency_blank(
        self,
        slug: str,
        *,
        created_by: str | None = None,
    ) -> dict[str, object]:
        # Publica HTML realmente vazio, preservando versões anteriores.
        await self._lock_page(slug)
        page = await self._page(slug, create=True)
        assert page is not None
        blank_html = (
            '<!doctype html>\\n'
            '<html lang="pt-BR">\\n<head>\\n'
            '<meta charset="utf-8">\\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\\n'
            '<meta name="scheduler-pro-template" content="emergency-blank">\\n'
            '<meta name="scheduler-pro-content-version" content="2">\\n'
            '<meta name="scheduler-pro-surface" content="landing">\\n'
            '<title>Página em branco</title>\\n'
            '<style>html,body{margin:0;min-height:100%;background:#fff}'
            '@media(max-width:680px){body{min-height:100dvh}}</style>\\n'
            '</head>\\n<body></body>\\n</html>'
        )
        content = HtmlTemplateContract.wrapper(
            blank_html,
            expected_surface="LANDING",
        )
        version = await self._create_version(
            page,
            content,
            created_by=created_by,
            label="Página em branco — emergência",
        )
        page.status = LandingPageStatus.published.value
        page.current_version_id = version.id
        page.draft_version_id = version.id
        page.template_key = "emergency-blank"
        await self.session.commit()
        return {
            "id": str(page.id),
            "status": page.status,
            "current_version_id": str(version.id),
            "version_number": version.version_number,
            "blank": True,
        }

'''
        source = source.replace(anchor, methods + anchor, 1)

    path.write_text(source, encoding='utf-8')


def patch_backend_routes(repo: Path) -> None:
    path = repo / BACKEND_ROUTES
    source = read(path)
    if '/emergency-rollback' in source and '/emergency-blank' in source:
        return
    anchor = '@router.post("/{slug}/duplicate")\n'
    if anchor not in source:
        fail('landing_pages.py divergiu: ponto para rotas de emergência não localizado.')
    routes = '''@router.post("/{slug}/emergency-rollback")
async def emergency_rollback(
    slug: str,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await LandingPageService(session).emergency_rollback(
        slug,
        created_by=principal.user_id,
    )
    return success(data)


@router.post("/{slug}/emergency-blank")
async def emergency_blank(
    slug: str,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await LandingPageService(session).emergency_blank(
        slug,
        created_by=principal.user_id,
    )
    return success(data)


'''
    source = source.replace(anchor, routes + anchor, 1)
    path.write_text(source, encoding='utf-8')


def remove_old_runtime(repo: Path) -> list[str]:
    removed: list[str] = []
    for relative in OLD_RUNTIME_FILES:
        path = repo / relative
        if path.exists():
            path.unlink()
            removed.append(str(relative))
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f'Instala ARGWS Visual Builder Universal {PACKAGE_VERSION} no Scheduler Pro em modo New-Only, com Project/Site Workspace multi-página, branding AVB e recuperação de publicação.'
    )
    parser.add_argument('repo', type=Path, help='Diretório raiz do scheduler-pro-platform')
    args = parser.parse_args()
    repo = args.repo.resolve()

    required = [
        repo / 'package.json',
        repo / 'apps/web/package.json',
        repo / 'apps/web/src/App.vue',
        repo / 'apps/web/src/PublicSitePage.vue',
        repo / BACKEND_SERVICE,
        repo / BACKEND_ROUTES,
    ]
    for path in required:
        if not path.exists():
            fail(f'Não parece ser um checkout compatível do Scheduler Pro: {path} ausente')

    backup_paths = required + [repo / p for p in OLD_RUNTIME_FILES] + [
        repo / 'apps/web/src/TenantVisualPageBuilder.vue',
        repo / 'apps/web/src/PublicVisualLandingRenderer.vue',
    ]
    backup_root = backup(repo, backup_paths)

    install_package(repo)
    shutil.copy2(HERE / 'TenantVisualPageBuilder.vue', repo / 'apps/web/src/TenantVisualPageBuilder.vue')
    shutil.copy2(HERE / 'PublicVisualLandingRenderer.vue', repo / 'apps/web/src/PublicVisualLandingRenderer.vue')
    patch_root_package(repo)
    patch_web_package(repo)
    patch_app(repo)
    patch_public_site(repo)
    patch_backend_service(repo)
    patch_backend_routes(repo)
    removed = remove_old_runtime(repo)

    print(f'ARGWS Visual Builder Universal {PACKAGE_VERSION} instalado em modo New-Only.')
    print(f'Backup pré-instalação: {backup_root}')
    if removed:
        print('Componentes antigos removidos do runtime:')
        for item in removed:
            print(f'  - {item}')
    print('Recuperação de emergência instalada:')
    print('  POST /api/v1/landing-pages/{slug}/emergency-rollback')
    print('  POST /api/v1/landing-pages/{slug}/emergency-blank')
    print('Próximos comandos:')
    print('  npm install')
    print('  npm run typecheck --workspace @scheduler-pro/web')
    print('  npm run build --workspace @scheduler-pro/web')
    print(f'Runtime final: somente ARGWS Visual Builder Universal {PACKAGE_VERSION}.')


if __name__ == '__main__':
    main()
