# -*- coding: utf-8 -*-
from __future__ import absolute_import
import functools

from scrapy.statscollectors import StatsCollector
from tornado.ioloop import PeriodicCallback

from arachnado.signals import Signal
from arachnado.utils.misc import decorate_methods
from arachnado.crawler.signals import SIGNALS


def store_changed_value(meth):
    @functools.wraps(meth)
    def wrapper(self, key, *args, **kwargs):
        old_value = self._stats.get(key)
        meth(self, key, *args, **kwargs)
        value = self._stats.get(key)
        if value != old_value:
            self._changes[key] = value
    return wrapper


def store_changed_stats(meth):
    @functools.wraps(meth)
    def wrapper(self, *args, **kwargs):
        meth(self, *args, **kwargs)
        self._changes = self._stats
    return wrapper


stats_changed = Signal("stats_changed", False)


@decorate_methods(["set_value", "inc_value", "max_value", "min_value"],
                  store_changed_value)
@decorate_methods(["set_stats", "clear_stats"], store_changed_stats)
class ArachnadoStatsCollector(StatsCollector):
    """
    Stats Collector which allows to subscribe to value changes.
    Update notifications are throttled: interval between updates is no shorter
    than ``accumulate_time``.

    It is assumed that stat keys are never deleted.
    """
    accumulate_time = 0.1  # value is in seconds

    def __init__(self, crawler):
        super(ArachnadoStatsCollector, self).__init__(crawler)
        self.crawler = crawler
        self._changes = {}
        self._task = PeriodicCallback(self.emit_changes,
                                      self.accumulate_time * 1000)
        self._task.start()

    def emit_changes(self):
        if self._changes:
            changes, self._changes = self._changes, {}
            self.crawler.signals.send_catch_log(SIGNALS['stats_changed'],
                                                changes=changes)

    def open_spider(self, spider):
        super(ArachnadoStatsCollector, self).open_spider(spider)
        self._task.start()

    def close_spider(self, spider, reason):
        super(ArachnadoStatsCollector, self).close_spider(spider, reason)
        self._task.stop()
