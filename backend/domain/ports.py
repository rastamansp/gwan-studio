from abc import ABC, abstractmethod
from .entities import Project, Source, Job, Thumbnail, SeoMetadata, HighlightMoment


class IObjectStoragePort(ABC):
    """Port para armazenamento de artefatos de vídeo."""

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """True para backends locais (filesystem); False para remotos (MinIO/S3)."""
        ...

    @abstractmethod
    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        """Armazena bytes diretamente (ex.: upload de arquivo pequeno)."""
        ...

    @abstractmethod
    def resolve_read_path(self, key: str) -> str:
        """Retorna caminho local para leitura. Para backends remotos, baixa para cache."""
        ...

    @abstractmethod
    def resolve_write_path(self, key: str) -> str:
        """Retorna caminho local para escrita com diretório pai criado.
        Para backends remotos, retorna caminho em diretório temporário."""
        ...

    @abstractmethod
    def finalize_write(self, key: str, local_path: str, content_type: str) -> None:
        """Persiste o arquivo após escrita. No-op para backend local."""
        ...

    @abstractmethod
    def object_exists(self, key: str) -> bool:
        """Verifica se o objeto existe no storage."""
        ...

    @abstractmethod
    def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        """Gera URL assinada de acesso temporário."""
        ...

    @abstractmethod
    def delete_object(self, key: str) -> None:
        """Remove objeto do storage."""
        ...


class IProjectRepository(ABC):
    @abstractmethod
    def save(self, project: Project) -> Project: ...

    @abstractmethod
    def get(self, project_id: str) -> Project: ...

    @abstractmethod
    def list(self, project_type: str | None = None) -> list[Project]: ...


class ISourceRepository(ABC):
    @abstractmethod
    def save(self, source: Source) -> Source: ...

    @abstractmethod
    def get(self, source_id: str) -> Source: ...

    @abstractmethod
    def list_by_project(self, project_id: str) -> list[Source]: ...

    @abstractmethod
    def delete(self, source_id: str) -> None: ...


class IJobRepository(ABC):
    @abstractmethod
    def save(self, job: Job) -> Job: ...

    @abstractmethod
    def get(self, job_id: str) -> Job: ...

    @abstractmethod
    def append_log(self, job_id: str, message: str) -> None: ...


class IAiVisionPort(ABC):
    @abstractmethod
    def analyze_frames(self, frames: list[bytes], prompt: str) -> dict: ...


class IAiTextPort(ABC):
    @abstractmethod
    def generate_seo(self, context: str, project: Project) -> SeoMetadata: ...


class IVideoWorkerPort(ABC):
    @abstractmethod
    def merge(self, source_keys: list[str], output_key: str) -> str: ...

    @abstractmethod
    def export(self, input_key: str, output_key: str, codec: str, bitrate: str) -> str: ...

    @abstractmethod
    def extract_frames(self, input_key: str, count: int) -> list[bytes]: ...


class IHighlightAnalysisPort(ABC):
    """F17 — análise semântica dos momentos de uma partida.

    Implementações reais fundem transcrição (Whisper, hoje delegado a um
    worker GPU externo — ver docs/spec/20-features/F17-futebol-highlights.md)
    com os picos de energia do áudio. A porta isola essa dependência do
    resto do pipeline, para que o adapter possa evoluir (Claude direto →
    fila RabbitMQ + worker GPU) sem tocar nos use cases.
    """

    @abstractmethod
    def detect_moments(
        self,
        energy_peaks: list[float],
        duration_sec: float,
        project_name: str,
        importancia_min: int,
    ) -> list[dict]:
        """Retorna lista de `{timestamp, tipo, descricao, importancia}`."""
        ...


class IYouTubePort(ABC):
    @abstractmethod
    def upload_video(self, video_key: str, metadata: SeoMetadata, thumbnail_key: str) -> str: ...


class IEventBusPort(ABC):
    @abstractmethod
    def publish(self, channel: str, event: dict) -> None: ...
