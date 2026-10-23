"""Locale-aware formatting of sizes, speeds, durations and dates."""

from PySide6.QtCore import QCoreApplication, QDateTime, QLocale


def size(value: float | None) -> str:
    if value is None:
        return ""
    return QLocale().formattedDataSize(int(value), 1, QLocale.DataSizeFormat.DataSizeSIFormat)


def speed(value: float | None) -> str:
    if not value:
        return ""
    return QCoreApplication.translate("formatting", "{size}/s").format(size=size(value))


def duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def eta(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return QCoreApplication.translate("formatting", "{time} left").format(time=duration(seconds))


def timestamp(epoch: float | None) -> str:
    if not epoch:
        return ""
    moment = QDateTime.fromSecsSinceEpoch(int(epoch))
    return QLocale().toString(moment, QLocale.FormatType.ShortFormat)
