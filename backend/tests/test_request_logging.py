import logging

from movie_companion.request_logging import RequestPathFilter, configure_request_logging


def test_access_log_hides_private_query_but_preserves_status():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/api/search/catalog?q=private+movie+preference&token=secret", "1.1", 200), None)
    assert RequestPathFilter().filter(record)
    rendered = record.getMessage()
    assert "/api/search/catalog HTTP/1.1" in rendered
    assert "200" in rendered
    assert "private" not in rendered and "secret" not in rendered


def test_configuration_is_idempotent_and_does_not_hide_other_logs():
    configure_request_logging()
    configure_request_logging()
    logger = logging.getLogger("uvicorn.access")
    assert sum(isinstance(item, RequestPathFilter) for item in logger.filters) == 1
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "ordinary status", (), None)
    assert RequestPathFilter().filter(record)
    assert record.getMessage() == "ordinary status"
