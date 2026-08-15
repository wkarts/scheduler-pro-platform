from app.core.responses import success


def test_success_contract():
    assert success({"ok": True}) == {"data": {"ok": True}, "meta": {}}
