import torch
import numpy as np
from ultralytics import YOLO
import cv2
from huggingface_hub import hf_hub_download
from PIL import Image
import pathlib
import logging

logger = logging.getLogger(__name__)

"""
Модуль выполняет:

1. загрузку YOLOv8 модели для детекции лиц
2. детекцию лица (ТОЛЬКО если на изображении одно лицо)
3. crop лица
4. resize + padding (letterbox)
5. перевод изображения в grayscale

Используется ТОЛЬКО для хранения снимков лица.
Не участвует в основном pipeline распознавания.
"""


def get_model(repo_id: str):
    """
    Загружает YOLOv8 модель с HuggingFace Hub.

    Args:
        repo_id: имя репозитория модели
                 например: arnabdhar/YOLOv8-Face-Detection

    Returns:
        YOLO модель
    """

    device = "cuda" if torch.cuda.is_available() else "cpu"
    device = "mps" if torch.backends.mps.is_available() else device

    model_path = hf_hub_download(
        repo_id=repo_id,
        filename="model.pt"
    )

    model = YOLO(model_path)
    model.to(device)
    logger.info(f"Модель {model_path} загружена на устройство {device}")
    return model


def detect_face(model, img, th=0.5):
    """
    Детектирует лицо на изображении.

    Работает ТОЛЬКО если на изображении ровно одно лицо.

    Args:
        model: YOLO модель
        img: PIL.Image
        th: порог уверенности

    Returns:
        face_crop (PIL.Image) или None
    """

    results = model.predict(img, stream=False, verbose=False)

    if not results:
        logger.info("YOLO не обнаружила лицo")
        return None

    result = results[0]
    boxes = result.boxes

    if boxes is None or len(boxes) == 0:
        logger.info("YOLO не обнаружила лицo")
        return None

    if len(boxes) > 1:
        logger.info(f"YOLO обнаружил {len(boxes)} лиц")
        return None

    box = boxes.xyxy.cpu().numpy()[0]
    score = boxes.conf.cpu().numpy()[0]

    if score < th:
        logger.info("Лицо неразборчиво")
        return None

    x1, y1, x2, y2 = map(int, box)

    face_crop = img.crop([x1, y1, x2, y2])
    return face_crop


def resize_face(face_img, target_size=(224, 224)):
    """
    Изменяет размер лица без искажения пропорций.

    Используется letterbox resize (padding).

    Args:
        face_img: PIL.Image или numpy
        target_size: итоговый размер

    Returns:
        numpy array (H × W × 3)
    """

    if isinstance(face_img, Image.Image):
        face_np = np.array(face_img)
    else:
        face_np = face_img

    h, w = face_np.shape[:2]

    if h == 0 or w == 0:
        return None

    target_w, target_h = target_size

    scale = min(target_w / w, target_h / h)

    new_w = int(w * scale)
    new_h = int(h * scale)

    face_resized = cv2.resize(face_np, (new_w, new_h))

    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)

    y_offset = (target_h - new_h) // 2
    x_offset = (target_w - new_w) // 2

    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = face_resized

    return canvas


def convert_to_grayscale(image):
    """
    Переводит RGB изображение в grayscale.

    Args:
        image: numpy array (H × W × 3)

    Returns:
        numpy array (H × W)
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    return gray


def image_preprocessing(image_path_or_array, model):
    """
    Полный pipeline обработки изображения.

    1. загрузка изображения
    2. детекция лица
    3. crop
    4. resize
    5. grayscale

    Args:
        image_path: путь к изображению
        model: YOLO модель

    Returns:
        grayscale лицо (H × W) или None
    """

    if isinstance(image_path_or_array, (str, pathlib.Path)):
        img_path = str(image_path_or_array)
        img = cv2.imread(img_path)
    else:
        img = image_path_or_array

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)

    face = detect_face(model, pil_img, th=0.5)

    if face is None:
        return None

    face_resized = resize_face(face, target_size=(224, 224))

    if face_resized is None:
        return None

    face_gray = convert_to_grayscale(face_resized)
    logger.info("Конвертация прошла успешно")
    return face_gray