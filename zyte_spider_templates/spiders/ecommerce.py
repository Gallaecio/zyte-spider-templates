from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

import scrapy
from pydantic import BaseModel, Field, field_validator
from scrapy import Request
from scrapy.crawler import Crawler
from scrapy_poet import DummyResponse
from scrapy_spider_metadata import Args
from zyte_common_items import ProbabilityRequest, Product, ProductNavigation

from zyte_spider_templates.documentation import document_enum
from zyte_spider_templates.spiders.base import (
    ARG_SETTING_PRIORITY,
    EXTRACT_FROM_FIELD,
    GEOLOCATION_FIELD,
    MAX_REQUESTS_FIELD,
    BaseSpider,
    BaseSpiderParams,
    ExtractFrom,
    Geolocation,
)
from zyte_spider_templates.utils import get_domain


@document_enum
class EcommerceCrawlStrategy(str, Enum):
    full: str = "full"
    """Follow most links within the domain of URL in an attempt to discover and
    extract as many products as possible."""

    navigation: str = "navigation"
    """Follow pagination, subcategories, and product detail pages."""

    pagination_only: str = "pagination_only"
    """Follow pagination and product detail pages. SubCategory links are
    ignored. Use this when some subCategory links are misidentified by
    ML-extraction."""


CRAWL_STRATEGY_FIELD = Field(
    title="Crawl strategy",
    description="Determines how the start URL and follow-up URLs are crawled.",
    default=EcommerceCrawlStrategy.navigation,
    json_schema_extra={
        "enumMeta": {
            EcommerceCrawlStrategy.full: {
                "title": "Full",
                "description": "Follow most links within the domain of URL in an attempt to discover and extract as many products as possible.",
            },
            EcommerceCrawlStrategy.navigation: {
                "title": "Navigation",
                "description": "Follow pagination, subcategories, and product detail pages.",
            },
            EcommerceCrawlStrategy.pagination_only: {
                "title": "Pagination Only",
                "description": (
                    "Follow pagination and product detail pages. SubCategory links are ignored. "
                    "Use this when some subCategory links are misidentified by ML-extraction."
                ),
            },
        },
    },
)


class EcommerceSpiderParams(BaseSpiderParams):
    crawl_strategy: EcommerceCrawlStrategy = CRAWL_STRATEGY_FIELD


class EcommerceSpider(Args[EcommerceSpiderParams], BaseSpider):
    """Yield products from an e-commerce website.

    *url* is the start URL, e.g. a homepage or category page.

    *crawl_strategy* determines how the start URL and follow-up URLs are
    crawled:

    -   ``"navigation"`` (default): follow pagination, subcategories, and
        product detail pages.

    -   ``"full"``: follow most links within the domain of *url* in an attempt to
        discover and extract as many products as it can.

    *geolocation* (optional) is an ISO 3166-1 alpha-2 2-character string specified in:
    https://docs.zyte.com/zyte-api/usage/reference.html#operation/extract/request/geolocation

    *max_requests* (optional) specifies the max number of Zyte API requests
    allowed for the crawl.

    *extract_from* (optional) allows to enforce extracting the data from
    either "browserHtml" or "httpResponseBody".
    """

    name = "ecommerce"

    metadata: Dict[str, Any] = {
        **BaseSpider.metadata,
        "title": "E-commerce",
        "description": "Template for spiders that extract product data from e-commerce websites.",
    }

    @classmethod
    def from_crawler(cls, crawler: Crawler, *args, **kwargs) -> scrapy.Spider:
        spider = super(EcommerceSpider, cls).from_crawler(crawler, *args, **kwargs)
        url = getattr(spider.args, "url", None)
        if url:
            spider.start_urls = [url]
        else:
            spider.start_urls = spider.args.urls
        spider.allowed_domains = [get_domain(url) for url in spider.start_urls]

        if spider.args.extract_from is not None:
            spider.settings.set(
                "ZYTE_API_PROVIDER_PARAMS",
                {
                    "productOptions": {"extractFrom": spider.args.extract_from},
                    "productNavigationOptions": {
                        "extractFrom": spider.args.extract_from
                    },
                    **spider.settings.get("ZYTE_API_PROVIDER_PARAMS", {}),
                },
                priority=ARG_SETTING_PRIORITY,
            )

        return spider

    def start_requests(self) -> Iterable[Request]:
        page_params = {}
        if self.args.crawl_strategy == EcommerceCrawlStrategy.full:
            page_params = {"full_domain": self.allowed_domains[0]}

        for url in self.start_urls:
            yield Request(
                url=url,
                callback=self.parse_navigation,
                meta={
                    "page_params": page_params,
                    "crawling_logs": {"page_type": "productNavigation"},
                },
            )

    def parse_navigation(
        self, response: DummyResponse, navigation: ProductNavigation
    ) -> Iterable[Request]:
        page_params = response.meta.get("page_params")

        products = navigation.items or []
        for request in products:
            yield self.get_parse_product_request(request)

        if navigation.nextPage:
            if not products:
                self.logger.info(
                    f"Ignoring nextPage link {navigation.nextPage} since there "
                    f"are no product links found in {navigation.url}"
                )
            else:
                yield self.get_nextpage_request(navigation.nextPage)

        if self.args.crawl_strategy != EcommerceCrawlStrategy.pagination_only:
            for request in navigation.subCategories or []:
                yield self.get_subcategory_request(request, page_params=page_params)

    def parse_product(
        self, response: DummyResponse, product: Product
    ) -> Iterable[Product]:
        probability = product.get_probability()

        # TODO: convert to a configurable parameter later on after the launch
        if probability is None or probability >= 0.1:
            yield product
        else:
            self.crawler.stats.inc_value("drop_item/product/low_probability")
            self.logger.info(
                f"Ignoring item from {response.url} since its probability is "
                f"less than threshold of 0.1:\n{product}"
            )

    @staticmethod
    def get_parse_navigation_request_priority(
        request: Union[ProbabilityRequest, Request]
    ) -> int:
        if (
            not hasattr(request, "metadata")
            or not request.metadata
            or request.metadata.probability is None
        ):
            return 0
        return int(100 * request.metadata.probability)

    def get_parse_navigation_request(
        self,
        request: Union[ProbabilityRequest, Request],
        callback: Optional[Callable] = None,
        page_params: Optional[Dict[str, Any]] = None,
        priority: Optional[int] = None,
        page_type: str = "productNavigation",
    ) -> scrapy.Request:
        callback = callback or self.parse_navigation

        return request.to_scrapy(
            callback=callback,
            priority=priority or self.get_parse_navigation_request_priority(request),
            meta={
                "page_params": page_params or {},
                "crawling_logs": {
                    "name": request.name or "",
                    "probability": request.get_probability(),
                    "page_type": page_type,
                },
            },
        )

    def get_subcategory_request(
        self,
        request: Union[ProbabilityRequest, Request],
        callback: Optional[Callable] = None,
        page_params: Optional[Dict[str, Any]] = None,
        priority: Optional[int] = None,
    ) -> scrapy.Request:
        page_type = "subCategories"
        request_name = request.name or ""
        if "[heuristics]" not in request_name:
            page_params = None
        else:
            page_type = "productNavigation-heuristics"
            request.name = request_name.replace("[heuristics]", "").strip()
        return self.get_parse_navigation_request(
            request,
            callback,
            page_params,
            priority,
            page_type,
        )

    def get_nextpage_request(
        self,
        request: Union[ProbabilityRequest, Request],
        callback: Optional[Callable] = None,
        page_params: Optional[Dict[str, Any]] = None,
    ):
        return self.get_parse_navigation_request(
            request, callback, page_params, self._NEXT_PAGE_PRIORITY, "nextPage"
        )

    def get_parse_product_request_priority(self, request: ProbabilityRequest) -> int:
        probability = request.get_probability() or 0
        return int(100 * probability) + self._NEXT_PAGE_PRIORITY

    def get_parse_product_request(
        self, request: ProbabilityRequest, callback: Optional[Callable] = None
    ) -> scrapy.Request:
        callback = callback or self.parse_product
        priority = self.get_parse_product_request_priority(request)

        probability = request.get_probability()

        scrapy_request = request.to_scrapy(
            callback=callback,
            priority=priority,
            meta={
                "crawling_logs": {
                    "name": request.name,
                    "probability": probability,
                    "page_type": "product",
                }
            },
        )
        scrapy_request.meta["allow_offsite"] = True
        return scrapy_request


class ExperimentalEcommerceSpiderParams(BaseModel):
    urls: List[str] = Field(
        title="URLs",
        description=(
            "Initial URLs for the crawl, separated by new lines. Enter the "
            "full URL including http(s), you can copy and paste it from your "
            "browser. Example: https://toscrape.com/"
        ),
    )
    crawl_strategy: EcommerceCrawlStrategy = CRAWL_STRATEGY_FIELD
    geolocation: Optional[Geolocation] = GEOLOCATION_FIELD
    max_requests: Optional[int] = MAX_REQUESTS_FIELD
    extract_from: Optional[ExtractFrom] = EXTRACT_FROM_FIELD

    @field_validator("urls", mode="before")
    @classmethod
    def split_lines(cls, value: Union[List[str], str]) -> List[str]:
        if isinstance(value, str):
            value = value.split("\n")
        return value


class ExperimentalEcommerceSpider(
    EcommerceSpider, Args[ExperimentalEcommerceSpiderParams]
):
    """Experimental alternative to :class:`EcommerceSpider`.

    *urls* are the start URLs, e.g. homepages or category pages, as a
    new-line-separated list. It replaces *url*.

    For other parameters, see :class:`EcommerceSpider`.
    """

    name = "experimental-ecommerce"

    metadata: Dict[str, Any] = {
        **EcommerceSpider.metadata,
        "title": "E-commerce (experimental)",
        "description": (
            "Experimental template for spiders that extract product data from "
            "e-commerce websites."
        ),
    }
