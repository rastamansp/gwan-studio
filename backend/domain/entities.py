from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


DEFAULT_HIGHLIGHT_SETTINGS = {
    'pre_roll': 6.0,
    'post_roll': 8.0,
    'merge_gap': 4.0,
    'top_n_peaks': 40,
    'importancia_min': 5,
}


@dataclass
class Project:
    id: str
    name: str
    channel_name: str
    phase: str
    project_type: str = 'gopro'  # gopro | futebol — ver F17
    highlight_settings: dict = field(default_factory=lambda: dict(DEFAULT_HIGHLIGHT_SETTINGS))
    owner_id: Optional[int] = None
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


@dataclass
class HighlightMoment:
    """Momento relevante detectado no pipeline de futebol (F17)."""
    id: str
    project_id: str
    source_id: Optional[str]
    timestamp_sec: float
    tipo: str  # gol | defesa | penalti | falta | expulsao | chance | outro
    descricao: str
    importancia: int  # 0-10
    included: bool = True
