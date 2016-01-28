# -*- coding: utf-8 -*-
"""
Async MongoDB item exporter using Motor_.

.. _Motor: https://github.com/mongodb/motor
"""
from __future__ import absolute_import
import json
import logging
import datetime

import scrapy
from tornado import gen
from scrapy.exceptions import NotConfigured

from arachnado.utils.twistedtornado import tt_coroutine
from arachnado.utils.misc import json_encode
from arachnado.utils.mongo import motor_from_uri


logger = logging.getLogger(__name__)


def scrapy_item_to_dict(son):
    """Recursively convert scrapy.Item to dict"""
    for key, value in son.items():
        if isinstance(value, (scrapy.Item, dict)):
            son[key] = scrapy_item_to_dict(
                son.pop(key)
            )
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, (scrapy.Item, dict)):
                    value[i] = scrapy_item_to_dict(item)
    return dict(son)


class MongoExportPipeline(object):
    """
    This pipeline exports tems to MongoDB using async mongo
    driver (motor). Interaction with MongoDB doesn't block
    the event loop.

    On start it creates object in 'jobs' collection and sets
    spider.motor_job_id to the ID of this job.

    If MONGO_EXPORT_JOBID_KEY option is set, job id is added to
    each stored item under the specified key name.
    """

    def __init__(self, crawler):
        self.crawler = crawler
        settings = self.crawler.settings
        if not settings.getbool('MONGO_EXPORT_ENABLED', False):
            raise NotConfigured

        self.job_id_key = settings.get('MONGO_EXPORT_JOBID_KEY')
        self.items_uri = settings.get('MONGO_EXPORT_ITEMS_URI')
        self.jobs_uri = settings.get('MONGO_EXPORT_JOBS_URI')
        self.items_client, _, _, _, self.items_col = \
            motor_from_uri(self.items_uri)
        self.jobs_client, _, _, _, self.jobs_col = \
            motor_from_uri(self.jobs_uri)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    @tt_coroutine
    def open_spider(self, spider):
        logger.debug("open_spider {}".format(spider.name))
        try:
            yield self.items_col.ensure_index(self.job_id_key)

            self.job_id = yield self.jobs_col.insert({
                'started_at': datetime.datetime.utcnow(),
                'spider': spider.name,
            })
            spider.motor_job_id = str(self.job_id)

            logger.info("Crawl job generated id: %s", self.job_id,
                        extra={'crawler': self.crawler})
        except Exception:
            self.job_id = None
            logger.error(
                "Can't connect to %s. Items won't be stored.",
                self.items_uri, exc_info=True,
                extra={'crawler': self.crawler},
            )

    @tt_coroutine
    def close_spider(self, spider):
        logger.debug("close_spider {}".format(spider.name))
        if self.job_id is None:
            self.jobs_client.close()
            self.items_client.close()
            return

        # json is to fix an issue with dots in key names
        stats = json_encode(self.crawler.stats.get_stats())

        yield self.jobs_col.update(
            {'_id': self.job_id},
            {'$set': {
                'finished_at': datetime.datetime.utcnow(),
                'stats': stats,
            }}
        )
        self.jobs_client.close()
        self.items_client.close()
        logger.info("Job info %s is saved", self.job_id,
                    extra={'crawler': self.crawler})

    @tt_coroutine
    def process_item(self, item, spider):
        mongo_item = scrapy_item_to_dict(item)
        if self.job_id_key:
            mongo_item[self.job_id_key] = self.job_id
        try:
            yield self.items_col.insert(mongo_item)
            self.crawler.stats.inc_value("mongo_export/items_stored_count")
        except Exception as e:
            self.crawler.stats.inc_value("mongo_export/store_error_count")
            self.crawler.stats.inc_value("mongo_export/store_error_count/" +
                                         e.__class__.__name__)
            logger.error("Error storing item", exc_info=True, extra={
                'crawler': self.crawler
            })
        raise gen.Return(item)
