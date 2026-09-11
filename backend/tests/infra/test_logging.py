"""统一日志配置。"""

import logging

from miles_core.logging import get_logger, setup_logging


def test_setup_logging_idempotent():
    setup_logging()
    setup_logging()
    logger = get_logger("tests.logging")
    logger.info("test message ok")
    assert logger.name == "tests.logging"
    assert logging.getLogger().handlers


def test_get_logger_auto_configures():
    name = "tests.logging.auto"
    before = logging.getLogger(name)
    assert before is get_logger(name)
