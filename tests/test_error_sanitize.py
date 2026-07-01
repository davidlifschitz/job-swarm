from ml_job_swarm.error_sanitize import sanitize_error_message


def test_sanitize_error_message_redacts_secrets():
    assert sanitize_error_message("invalid token abc") == "[redacted]"


def test_sanitize_error_message_truncates_long_text():
    message = "x" * 1000
    assert len(sanitize_error_message(message)) == 500
