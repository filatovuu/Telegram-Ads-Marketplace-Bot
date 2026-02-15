import pytest


@pytest.mark.asyncio
async def test_start_handler_exists():
    """Verify the start router and command handler are importable and configured."""
    from handlers.start import router

    assert router.name == "start"
    assert router.message.handlers


@pytest.mark.asyncio
async def test_callbacks_router_exists():
    """Verify the callbacks router is importable and has handlers."""
    from handlers.callbacks import router

    assert router.name == "callbacks"
    assert router.callback_query.handlers


@pytest.mark.asyncio
async def test_messages_templates_available():
    """Verify message templates are defined for required locales."""
    from templates.messages import MESSAGES

    assert "en" in MESSAGES
    assert "ru" in MESSAGES

    required_keys = ["welcome", "help", "no_deals", "btn_open_app", "btn_my_deals", "btn_help"]
    for lang in ("en", "ru"):
        for key in required_keys:
            assert key in MESSAGES[lang], f"Missing key '{key}' in '{lang}' messages"


@pytest.mark.asyncio
async def test_middlewares_importable():
    """Verify middleware classes are importable."""
    from middleware.auth import AuthMiddleware
    from middleware.i18n import I18nMiddleware

    assert AuthMiddleware is not None
    assert I18nMiddleware is not None
