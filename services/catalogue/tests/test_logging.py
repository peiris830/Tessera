import logging

from app.logging_config import QUIET_LOGGERS, configure_logging


def test_third_party_info_logs_are_suppressed_but_warnings_kept():
    configure_logging("catalogue", "INFO")  # app.main already did this at import; idempotent

    for name in QUIET_LOGGERS:
        logger = logging.getLogger(f"{name}.child")  # e.g. mangum.http, botocore.credentials
        assert not logger.isEnabledFor(logging.INFO)
        assert logger.isEnabledFor(logging.WARNING)


def test_our_own_logger_still_logs_info():
    configure_logging("catalogue", "INFO")
    assert logging.getLogger("catalogue").isEnabledFor(logging.INFO)
