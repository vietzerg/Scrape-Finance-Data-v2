
# FAD Redis spider - the project's RedisSpiders should be based on this

import os
import redis
from scrapy.exceptions import DontCloseSpider
from scrapy.utils.log import configure_logging
from scrapy_redis.spiders import RedisSpider
from scrapy_redis.utils import bytes_to_str
from scraper_vietstock.spiders.models.constants import ERROR_SET_SUFFIX, REDIS_HOST
from scraper_vietstock.spiders.models.corporateaz import closed_redis_key as corpAZ_closed_key


class scraperVSRedisSpider(RedisSpider):
    '''
    Base RedisSpider for other spiders in this project
    '''

    def __init__(self, *args, **kwargs):
        super(scraperVSRedisSpider, self).__init__(*args, **kwargs)
        self.r = redis.Redis(host=REDIS_HOST, decode_responses=True)
        self.report_types = []

        self.error_set_key = f'{self.name}:{ERROR_SET_SUFFIX}'
        self.corpAZ_closed_key = corpAZ_closed_key
        self.statusfilepath = f'run/scrapy/{self.name}.scrapy'
        
        os.makedirs(os.path.dirname(self.statusfilepath), exist_ok=True)
        with open(self.statusfilepath, 'w') as statusfile:
            statusfile.write('running')
            statusfile.close()

    def spider_idle(self):
        '''
        Overrides default method
        '''

        self.idling = True
        self.logger.info("=== IDLING... ===")
        self.schedule_next_requests()
        raise DontCloseSpider

    def handle_error(self, failure):
        '''
        If there's an error with a request/response, add it to the error set
        '''

        if failure.request:
            request = failure.request
            ticker = request.meta['ticker']
            report_type = request.meta['ReportType']
            try:
                page = request.meta['Page']
            except:
                page = "1"

            self.logger.info(
                f'=== ERRBACK: on request for ticker {ticker}, report {report_type}, on page {page}')

        elif failure.value.response:
            response = failure.value.response
            ticker = response.meta['ticker']
            report_type = response.meta['ReportType']
            try:
                page = response.meta['Page']
            except:
                page = "1"

            self.logger.info(
                f'=== ERRBACK: on response for ticker {ticker}, report {report_type}, on page {page}')
        
        # Write error to log file
        with open(
            f'logs/{self.name}_{report_type}_spidererrors_short.log', 'a+') as openfile:
            openfile.write(
                f'ticker: {ticker}, report: {report_type}, page {page}, error type: {str(failure.type)} \n')
        
        # Add error to Redis set if the function is defined
        if getattr(self, "handle_error_redis", None):
            getattr(self, "handle_error_redis")(ticker, page, report_type)

    def handle_error_redis(self, ticker, page, report_type):
        '''
        Add errors to Redis error set
        '''

        self.r.sadd(self.error_set_key, f'{ticker};{report_type};{page}')

    def close_status(self):
        '''
        Clear running status file after closing
        '''

        if os.path.exists(self.statusfilepath):
            os.remove(self.statusfilepath)
            self.logger.info(f'Deleted status file at {self.statusfilepath}')
