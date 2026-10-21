"""Keep query strings out of Uvicorn request logs."""
import logging


class RequestPathFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn logs client, method, path-with-query, HTTP version and status.
        if isinstance(record.args, tuple) and len(record.args) == 5 and isinstance(record.args[2], str):
            args = list(record.args)
            args[2] = args[2].split("?", 1)[0]
            record.args = tuple(args)
        return True


def configure_request_logging():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RequestPathFilter) for item in logger.filters):
        logger.addFilter(RequestPathFilter())
