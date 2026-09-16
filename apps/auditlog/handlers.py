import logging
import traceback

from django.utils.log import CallbackFilter


class DatabaseLogHandler(logging.Handler):
    """
    Writes logging records at ERROR+ into the SystemLog database table.
    No file handlers — database is the system of record for errors.
    """

    def emit(self, record):
        try:
            # Avoid recursion if SystemLog write fails and logs again
            if getattr(record, "skip_db_log", False):
                return
            if record.name.startswith("django.db"):
                return

            from apps.core.logging_utils import log_event

            tb = ""
            if record.exc_info:
                tb = "".join(traceback.format_exception(*record.exc_info))

            context = {
                "logger": record.name,
                "pathname": getattr(record, "pathname", ""),
                "lineno": getattr(record, "lineno", None),
                "funcName": getattr(record, "funcName", ""),
            }
            if tb:
                # log_event with exc=None but we pass traceback via a workaround:
                # create entry then update traceback if needed
                pass

            entry = log_event(
                record.levelname,
                record.name[:100],
                "OTHER",
                record.getMessage(),
                context=context,
            )
            if entry and tb and not entry.traceback:
                entry.traceback = tb
                entry.save(update_fields=["traceback"])
        except Exception:
            self.handleError(record)
