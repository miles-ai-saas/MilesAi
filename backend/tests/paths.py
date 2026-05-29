"""测试用路径常量（子目录内勿用 ``Path(__file__).parents[1]`` 猜 backend 根）。"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
