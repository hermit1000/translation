from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class Content:
    text: str
    description: Optional[str] = None

    @classmethod
    def parse(cls, sentence: Union[str, Content]) -> Content:
        if isinstance(sentence, cls):
            return sentence

        text, separator, description = sentence.partition("#")
        return cls(text=text, description=description if separator else None)

    @property
    def is_hex(self) -> bool:
        return self.text.startswith("0x:")

    @property
    def hex_codes(self) -> str:
        if not self.is_hex:
            raise ValueError("Content is not hex-only.")
        return self.text[3:]

    def serialize(self) -> str:
        if self.description is None:
            return self.text
        return f"{self.text}#{self.description}"

    def copy(self) -> Content:
        return Content(text=self.text, description=self.description)

    def __str__(self) -> str:
        return self.serialize()
