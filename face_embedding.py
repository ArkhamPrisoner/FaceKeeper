import cv2
import numpy as np
from insightface.app import FaceAnalysis
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FaceEmbedding:
    def __init__(self, model_name='buffalo_l', det_size=(640, 640), det_thresh=0.5):

        self.app = FaceAnalysis(
            name=model_name,
            allowed_modules=['detection', 'recognition'],
            root='~/.insightface',
            providers=['CPUExecutionProvider']
        )

        self.app.prepare(
            ctx_id=-1,
            det_size=det_size,
            det_thresh=det_thresh
        )

        logger.info(
            f"FaceAnalysis загружен: {model_name} | "
            f"det_size={det_size} det_thresh={det_thresh}"
        )

    def get_embedding(self, image_path_or_array):

        try:

            # загрузка изображения
            if not isinstance(image_path_or_array, np.ndarray):

                img = cv2.imread(str(image_path_or_array))

                if img is None:
                    logger.error(f"Не удалось загрузить: {image_path_or_array}")
                    return None

            else:
                img = image_path_or_array

            faces = self.app.get(img)

            if len(faces) == 0:
                logger.info("FaceAnalysis не нашел лиц")
                return None

            if len(faces) > 1:
                logger.info(f"FaceAnalysis нашел {len(faces)} лиц")
                return None

            face = faces[0]

            embedding = face.normed_embedding.astype(np.float32)

            return embedding

        except Exception as e:

            logger.error(f"Ошибка получения embedding: {e}")

            return None