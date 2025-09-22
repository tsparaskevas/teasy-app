from __future__ import annotations
from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, Literal, Dict

SelectorType = Literal["css", "xpath"]
CategoryType = Literal["all", "search", "opinion", "other"]
SearchTermMode = Literal["raw", "greeklish"]

class Selector(BaseModel):
    type: SelectorType = "css"
    query: str
    attr: Optional[str] = None

class Pagination(BaseModel):
    mode: Literal["param", "path", "none"] = "param"
    param: str = "page"
    first_page: int = 1
    per_page: Optional[int] = None
    template: Optional[str] = None
    template_vars: Dict[str, str] = Field(default_factory=dict)

class FieldMap(BaseModel):
    title: Selector
    url: Selector
    date: Optional[Selector] = None
    summary: Optional[Selector] = None
    section: Optional[Selector] = None
    source: Optional[str] = None

class ScraperSpec(BaseModel):
    name: str
    base_url: HttpUrl
    start_url: HttpUrl
    selectors: FieldMap
    pagination: Pagination = Field(default_factory=Pagination)
    max_pages: int = 1
    js_required: bool = False
    notes: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)

    category: CategoryType = "all"
    is_chronological: bool = True
    search_term_mode: Optional[SearchTermMode] = None
    search_term_map: Dict[str, str] = Field(default_factory=dict)

    main_container_css: Optional[str] = None
    item_css: Optional[str] = None

    @field_validator("max_pages")
    @classmethod
    def _check_max_pages(cls, v):
        if v < 1:
            raise ValueError("max_pages must be >= 1")
        return v
