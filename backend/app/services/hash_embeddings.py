import math
import re
from collections import Counter

from langchain_core.embeddings import Embeddings


class HashEmbeddings(Embeddings):
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-zA-Z0-9-]+", text.lower())
        counts = Counter(tokens)
        if not counts:
            return vector

        for token, count in counts.items():
            index = hash(token) % self.dimensions
            vector[index] += float(count)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
