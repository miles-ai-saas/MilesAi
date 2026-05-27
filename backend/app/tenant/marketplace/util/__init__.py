"""
市场打包用内置 RAG 流程模板加载。

委托 ``flow_runtime.templates.registry``；结构说明见 ``templates/README.md``。
"""

from app.flow_runtime.templates.registry import load_flow_template_graph, load_rag_graph_template

__all__ = ["load_flow_template_graph", "load_rag_graph_template"]
