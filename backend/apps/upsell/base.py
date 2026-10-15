from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class Suggestion:
    strategy: str
    type: str
    headline: str
    reason_code: str
    score: float
    product: object = None
    data: dict = field(default_factory=dict)


class UpsellStrategy(ABC):
    key: ClassVar[str]

    @abstractmethod
    def suggest(self, view, config: dict) -> list[Suggestion]: ...
