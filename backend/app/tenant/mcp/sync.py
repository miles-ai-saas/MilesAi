"""
兼容导入：历史 ``from app.tenant.mcp.sync import fetch_mcp_tools``。

实现已集中在 ``client.fetch_mcp_tools``；新代码请直接 import client。
"""

from app.tenant.mcp.client import fetch_mcp_tools

__all__ = ["fetch_mcp_tools"]
