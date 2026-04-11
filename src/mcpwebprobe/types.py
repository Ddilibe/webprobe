#!/usr/bin/env python3
from dataclasses import dataclass


@dataclass(kw_only=True)
class SearchResult:
    url: str
    title: str
    description: str
    source: str
    engine: str
