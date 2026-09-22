"""sync 引擎应写入 Settings 中的池参数。"""

from unittest.mock import MagicMock, patch

from miles_core.config import Settings
from miles_core.infra.db import sync as sync_mod


def test_build_sync_engine_passes_pool_settings():
    settings = Settings(
        secret_key="x" * 32,
        db_pool_size=7,
        db_max_overflow=3,
        db_pool_timeout=11,
    )
    with patch.object(sync_mod, "create_engine") as create:
        create.return_value = MagicMock()
        sync_mod.build_sync_engine(settings)
    create.assert_called_once()
    args, kwargs = create.call_args
    assert args[0] == settings.database_url_sync
    assert kwargs["pool_size"] == 7
    assert kwargs["max_overflow"] == 3
    assert kwargs["pool_timeout"] == 11
    assert kwargs["pool_pre_ping"] is True
