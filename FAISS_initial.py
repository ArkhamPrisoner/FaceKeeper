import faiss
import numpy as np
import os
import logging
from bson import ObjectId
import secrets

logger = logging.getLogger(__name__)

"""Данный класс создан для создания и администрирования
векторной БД FAISS"""

class FaissManager:
    """Инициализируем создание векторной БД FAISS.
    Входные данные:
    index_path - название ранее созданной БД в корневой папке, не стоит трогать ни при каких условиях,
    название flat.index беретс везде по умолчанию и в документации.
    dim - размерность векторов в индексе брать исключительно 512, так как модель insightface buffalo_l возвращает 512,
    при изменении модель стоит менять dim
    similarity_threshold - порог схожести лиц, при котором модель считает лицо одинаковыми

    Выходные данные:

    """
    def __init__(self, index_path="flat.index", dim=512, similarity_threshold=0.7):
        self.index_path = index_path
        self.dim = dim
        self.similarity_threshold = similarity_threshold

        self.index = self._load_or_create_index()

    """Проверяет, было ли ранее создана БД
    Входные данные:
    Выходные данные:
    index - индекс FAISS
    """
    def _load_or_create_index(self):
        # Проверяет, есть ли БД, если папка существует, по читает индекс из нее
        # В противном случае создает БД с нуля
        if os.path.exists(self.index_path):
            index = faiss.read_index(self.index_path)
            # Проверка существующей размерности и необходимой размерности
            if index.d != self.dim:
                raise ValueError(
                    f"Размерность индекса {index.d} != {self.dim}"
                )

            logger.info(
                f"Индекс загружен: {self.index_path} | "
                f"векторов: {index.ntotal}"
            )
        else:
            index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))
            logger.info("Создан новый FAISS индекс")

        return index

    def _normalize(self, embeddings: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / np.maximum(norms, 1e-10)

    def _prepare_embedding(self, embedding):
        emb = np.array(embedding).astype(np.float32)

        if emb.ndim == 1:
            emb = emb.reshape(1, -1)

        if emb.shape[1] != self.dim:
            raise ValueError(f"Embedding должен быть размерности {self.dim}")

        return self._normalize(emb)

    def add_embedding(self, embedding):
        emb = self._prepare_embedding(embedding)

        if self.index.ntotal > 0:
            scores, indices = self.index.search(emb, 1)
            best_score = scores[0][0]

            if best_score > self.similarity_threshold:
                logger.info(
                    f"Лицо уже существует (similarity={best_score:.3f})"
                )
                return None
        
        index_id = secrets.randbits(63)


        self.index.add_with_ids(
            emb,
            np.array([index_id], dtype=np.int64)
        )

        logger.info("Добавлено новое лицо")

        return index_id

    def search(self, query_embedding, k=5):
        if self.index.ntotal == 0:
            logger.warning("Индекс пуст")
            return None, None

        query = self._prepare_embedding(query_embedding)

        scores, indices = self.index.search(query, k)

        best_score = float(scores[0][0])
        best_id = int(indices[0][0])

        return best_score, best_id

    def save(self):
        faiss.write_index(self.index, self.index_path)
        logger.info(f"Индекс сохранён: {self.index_path}")

    def get_stats(self):
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.index.d,
            "is_trained": self.index.is_trained,
            "index_type": type(self.index).__name__,
        }
    
    def remove_embedding(self, index_id):
        ids = np.array([index_id], dtype=np.int64)
        removed = self.index.remove_ids(ids)

        if removed:
            logger.info(f"Удалён ID={index_id}")
            return True
        return False