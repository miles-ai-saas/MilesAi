"""pytest 全局 fixture / 环境。"""

import os

# LiteLLM 在 import 时会尝试预加载 AWS Bedrock/SageMaker schema；未装 botocore 时会打 WARNING。
os.environ.setdefault("LITELLM_LOG", "ERROR")
