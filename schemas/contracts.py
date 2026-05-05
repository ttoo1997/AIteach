from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class RetrievalHit:
    id: str
    question: str
    answer: str
    source: str
    line_number: int
    embedding_score: float = 0.0
    lexical_score: float = 0.0
    formula_score: float = 0.0
    score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalResponse:
    question: str
    answer: str
    sources: List[str]
    confidence: float
    answer_type: str
    similar_questions: List[Dict[str, Any]]
    total_matches: int
    timestamp: str
    kb_path: str
    loaded_files: List[str]
    embedding_enabled: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.update(self.metadata)
        return payload


@dataclass
class SolveResult:
    success: bool
    extracted_text: Optional[str]
    solution: str
    image_path: Optional[str]
    error: Optional[str]
    analysis: str = ""
    review_notes: str = ""
    confidence: int = 0
    knowledge_hits: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.update(self.metadata)
        return payload


@dataclass
class SimulationResult:
    backend: str
    slip: np.ndarray
    torque: np.ndarray
    max_slip: float
    max_torque: float
    start_torque: float
    notes: List[str] = field(default_factory=list)
    plot_image_data_url: Optional[str] = None
    plot_caption: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "backend": self.backend,
            "slip": self.slip,
            "torque": self.torque,
            "max_slip": self.max_slip,
            "max_torque": self.max_torque,
            "start_torque": self.start_torque,
            "notes": list(self.notes),
        }
        if self.plot_image_data_url:
            payload["plot_image_data_url"] = self.plot_image_data_url
        if self.plot_caption:
            payload["plot_caption"] = self.plot_caption
        return payload
