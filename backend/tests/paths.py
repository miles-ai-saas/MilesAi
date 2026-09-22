"""测试用路径常量（子目录内勿用 ``Path(__file__).parents[N]`` 猜 backend 根）。

目录深度随「按包镜像」的层级变化，``parents[N]`` 会静默指错，故一律用本模块常量。
"""

from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = TESTS_ROOT.parent
PACKAGES = BACKEND_ROOT / "packages"
MILES_AI = PACKAGES / "miles-ai" / "src" / "miles_ai"
MILES_INTEGRATIONS = PACKAGES / "miles-integrations" / "src" / "miles_integrations"
MILES_SERVER = PACKAGES / "miles-server" / "src" / "miles_server"
