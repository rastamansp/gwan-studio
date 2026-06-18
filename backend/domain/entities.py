from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Project:
    id: str
    name: str
    channel_name: str
    phase: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


@dataclass
class Source:
    id: str
    project_id: str
    original_filename: str
    camera: str
    duration_sec: int
    size_bytes: int
    status: str  # uploading | ready | error
    storage_key: Optional[str] = None


@dataclass
class Job:
    id: str
    project_id: str
    job_type: str  # merge | export | thumbnail | seo | publish
    status: str  # pending | running | done | failed
    logs: list[str] = field(default_factory=list)
    result: Optional[dict] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Thumbnail:
    id: str
    project_id: str
    variant: str  # A | B | C
    storage_key: str
    selected: bool = False


@dataclass
class SeoMetadata:
    project_id: str
    title: str
    description: str
    tags: list[str]
    approved: bool = False
