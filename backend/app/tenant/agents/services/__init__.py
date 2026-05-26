"""
智能体域业务服务层。

- ``agent/``：核心 ``AgentService``（CRUD + 对话编排），对外 import 见 ``agent.__init__``。
- ``architecture`` / ``schedule`` / ``stats``：独立 Service，与 ``agent`` 聚合并列。
- ``context`` / ``sub_agents``：跨聚合共享，勿移入 ``agent/`` 子包以免循环依赖。

约定见 ``backend/README.md`` § services/ 子包（按聚合拆分）。
"""
