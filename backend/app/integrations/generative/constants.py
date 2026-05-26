"""生成类 ``ModelConfig.extra`` 键与 ``invoke_mode`` 常量。"""

from app.common.constants.model_extra import EXTRA_INVOKE_MODE

# --- 生图 extra ---
EXTRA_IMAGE_SIZE = "image_size"
EXTRA_IMAGE_STYLE = "image_style"

INVOKE_OPENAI_IMAGES = "openai_images"
INVOKE_DASHSCOPE_T2I = "dashscope_t2i"
INVOKE_DASHSCOPE_T2V = "dashscope_t2v"
INVOKE_VOLCENGINE_VIDEO = "volcengine_video"

# --- 生视频 extra / 轮询 ---
EXTRA_VIDEO_RESOLUTION = "video_resolution"
EXTRA_VIDEO_DURATION = "video_duration"
EXTRA_VIDEO_RATIO = "video_ratio"
EXTRA_VIDEO_SUBMIT_PATH = "video_submit_path"
EXTRA_VIDEO_POLL_PATH = "video_poll_path"
EXTRA_GENERATE_AUDIO = "generate_audio"
EXTRA_WATERMARK = "watermark"
EXTRA_POLL_INTERVAL_SEC = "poll_interval_sec"
EXTRA_POLL_TIMEOUT_SEC = "poll_timeout_sec"

DEFAULT_IMAGE_SIZE = "1024x1024"
MAX_IMAGES_PER_REQUEST = 4

DEFAULT_VIDEO_RESOLUTION = "720P"
DEFAULT_VIDEO_DURATION_SEC = 5
DEFAULT_POLL_INTERVAL_SEC = 3.0
DEFAULT_POLL_TIMEOUT_SEC = 600.0
