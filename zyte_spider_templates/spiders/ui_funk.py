import re
from logging import getLogger
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator
from scrapy import Spider
from scrapy_spider_metadata import Args

from ..utils import _URL_PATTERN

logger = getLogger(__name__)


class UIFunkSpiderParams(BaseModel):
    class Config:
        json_schema_extra = {
            "groups": [
                {
                    "id": "exclusive",
                    "title": "exclusive",
                    "widget": "exclusive",
                },
                {
                    "id": "exclusive[0].inclusive",
                    "title": "exclusive[0].inclusive",
                },
                {
                    "id": "exclusive[1].inclusive",
                    "title": "exclusive[1].inclusive",
                },
                {
                    "id": "inclusive",
                    "title": "inclusive",
                },
                {
                    "id": "inclusive[0].exclusive",
                    "title": "inclusive[0].exclusive",
                    "widget": "exclusive",
                },
                {
                    "id": "inclusive[1].exclusive",
                    "title": "inclusive[1].exclusive",
                    "widget": "exclusive",
                },
            ],
        }

    urls: Optional[List[str]] = Field(
        title="URLs",
        description=(
            "Should ignore empty lines, lines with invalid URLs will trigger "
            "a warning and be ignored as well, and the spider will fail with "
            "a ValueError exception if the parameter is not empty but after "
            "parsing the argument no valid URL is found."
        ),
        default=None,
        json_schema_extra={
            "widget": "textarea",
        },
    )

    @field_validator("urls", mode="before")
    @classmethod
    def validate_url_list(cls, value: Union[List[str], str]) -> List[str]:
        """Validate a list of URLs.
        If a string is received as input, it is split into multiple strings
        on new lines.
        List items that do not match a URL pattern trigger a warning and are
        removed from the list. If all URLs are invalid, validation fails.
        """
        if isinstance(value, str):
            value = value.split("\n")
        if not value:
            return value
        result = []
        for v in value:
            v = v.strip()
            if not v:
                continue
            if not re.search(_URL_PATTERN, v):
                logger.warning(
                    f"{v!r}, from the 'urls' spider argument, is not a "
                    f"valid URL and will be ignored."
                )
                continue
            result.append(v)
        if not result:
            raise ValueError(f"No valid URL found in {value!r}")
        return result

    textarea: Optional[str] = Field(
        title="textarea",
        default=None,
    )

    exclusive_0_inclusive_0: Optional[str] = Field(
        title="exclusive[0].inclusive[0]",
        default=None,
        json_schema_extra={
            "exclusiveRequired": True,
            "group": "exclusive[0].inclusive",
        },
    )
    exclusive_0_inclusive_1: Optional[str] = Field(
        title="exclusive[0].inclusive[1]",
        default=None,
        json_schema_extra={
            "group": "exclusive[0].inclusive",
        },
    )
    exclusive_1_inclusive_0: Optional[str] = Field(
        title="exclusive[1].inclusive[0]",
        default=None,
        json_schema_extra={
            "exclusiveRequired": True,
            "group": "exclusive[1].inclusive",
        },
    )
    exclusive_1_inclusive_1: Optional[str] = Field(
        title="exclusive[1].inclusive[1]",
        default=None,
        json_schema_extra={
            "group": "exclusive[1].inclusive",
        },
    )
    inclusive_0_exclusive_0: Optional[str] = Field(
        title="inclusive[0].exclusive[0]",
        default=None,
        json_schema_extra={
            "exclusiveRequired": True,
            "group": "inclusive[0].exclusive",
        },
    )
    inclusive_0_exclusive_1: Optional[str] = Field(
        title="inclusive[0].exclusive[1]",
        default=None,
        json_schema_extra={
            "group": "inclusive[0].exclusive",
        },
    )
    inclusive_1_exclusive_0: Optional[str] = Field(
        title="inclusive[1].exclusive[0]",
        default=None,
        json_schema_extra={
            "exclusiveRequired": True,
            "group": "inclusive[1].exclusive",
        },
    )
    inclusive_1_exclusive_1: Optional[str] = Field(
        title="inclusive[1].exclusive[1]",
        default=None,
        json_schema_extra={
            "group": "inclusive[1].exclusive",
        },
    )


class UIFunkSpider(Args[UIFunkSpiderParams], Spider):
    name = "ui_funk"
    metadata: Dict[str, Any] = {
        "template": True,
        "title": "UI funk",
        "description": (
            "Template to have fun testing new parameter syntax for UI " "integration."
        ),
    }
    start_urls = ["data:,"]

    def parse(self, response):
        yield self.args.dict()
