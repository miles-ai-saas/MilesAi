"""模型用量测试的共享替身。

``_ShortSession`` 与 ``_cm`` 原先被逐字复制在 ``test_chat_usage_sink_session.py`` 与
``test_chat_usage_accumulation.py``：两处都要随 ``AsyncSessionLocal`` 的用法同步演进。
2026-09-14 人工裁决后收敛到本模块，两个测试文件改为 import，不再逐文件复制。

文件名以 ``_`` 开头且不匹配 ``test_*.py``，pytest 不会将其作为测试模块收集。
"""


class _ShortSession:
    """替身：记录 add 的行，并记录是否 commit。"""

    def __init__(self) -> None:
        self.rows: list[object] = []
        self.commits = 0

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class _cm:
    """最小 async context manager（AsyncSessionLocal 的替身）。"""

    def __init__(self, session: object) -> None:
        self._session = session
        self.enters = 0

    async def __aenter__(self) -> object:
        self.enters += 1
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False
