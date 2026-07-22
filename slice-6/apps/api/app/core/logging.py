"""Structured JSON logging. Never log tokens, passwords, or user content."""
import logging

import structlog


def configure_logging(env: str) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if env == "development" else logging.INFO
        ),
    )
