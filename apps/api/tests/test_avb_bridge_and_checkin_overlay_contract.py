import re
from pathlib import Path


def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "web" / "src").is_dir():
            return parent
    return None


def _read(relative: str) -> str:
    root = _repo_root()
    if root is None:
        import pytest

        pytest.skip("Fontes Web não estão presentes nesta imagem isolada da API.")
    return (root / relative).read_text(encoding="utf-8")


def test_html_template_bridge_never_posts_vue_proxy_directly() -> None:
    source = _read("apps/web/src/HtmlTemplateFrame.vue")

    assert "function cloneForBridge(value:any):any" in source
    assert "JSON.stringify(value)" in source
    assert "function postToFrame(message:Record<string,unknown>):void" in source
    assert "target.postMessage(cloneForBridge(message),'*')" in source

    assert "const respond=(ok:boolean,value:any,message='')=>postToFrame(" in source
    assert "if(data.action==='context.get'){respond(true,props.context||{});return}" in source
    assert "if(data.action==='branding.get'){respond(true,(props.context as any)?.branding||{});return}" in source
    assert "if(data.action==='features.get'){respond(true,(props.context as any)?.features||{});return}" in source
    assert "function pushContext():void{postToFrame({type:'scheduler-pro-context',context:props.context||{}})}" in source

    assert "contentWindow?.postMessage({type:'scheduler-pro-context',context:props.context||{}},'*')" not in source
    assert "target.postMessage({type:'argws-runtime-response',id:data.id,ok,data:value,message},'*')" not in source


def test_agenda_operator_is_above_fullscreen_checkin_surface() -> None:
    css = _read("apps/web/src/tenant-overlay-layering.css")
    main = _read("apps/web/src/main.ts")

    operator_match = re.search(r"\.sp-agenda-operator-backdrop\s*\{[^}]*z-index:\s*(\d+)", css, re.S)
    checkin_match = re.search(r"\.sp-checkin-center\s*\{[^}]*z-index:\s*(\d+)", css, re.S)

    assert operator_match is not None
    assert checkin_match is not None
    assert int(operator_match.group(1)) > int(checkin_match.group(1))
    assert "import './tenant-overlay-layering.css'" in main
