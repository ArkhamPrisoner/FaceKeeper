import datetime
from bson import ObjectId
import numpy as np
from bson.binary import Binary
import zlib
import logging
logger = logging.getLogger(__name__)

class Employee:
    """ Класс создан исключительно для вставики данных в MongoDB"""
    def __init__(self, name, surname, patronymic, title, access_level, image, contacts, id_index, salary):
        """
        - face_id: уникальный ID - Создается автоматически
        - name: имя человека - задается пользователем в конструкторе
        - surname: фамилия человека - задается пользователем в конструкторе
        - patronymic: отчество человека - задается пользователем в конструкторе
        - full_name: Фамилия И.О - создается автоматически
        - title: должность - задается пользователем в конструкторе
        - access_level: уровень доступа - задается пользователем в конструкторе
        - image: вырезанное лицо - передается YOLO
        - hiring_date: дата найма - создается автоматически
        - contacts["email", "phone"]: Контактная информация - задается пользователем в конструкторе
        - cabinet/building/car ...: место нахождения работника - плавающая обязательная переменная
        - other: другая информация - уникальные поля
        """
        self.name = name
        self.surname = surname
        self.patronymic = patronymic
        self.title = title
        self.access_level = access_level
        self.image = image
        self.contacts = contacts
        self.full_name = (surname + " " + name + " " + patronymic)
        self.id_index = id_index
        self.salary = salary
        self.hiring_date = datetime.datetime.now()
        logger.info("Сущность пользователя создана")

    def set_place_of_work(self, place_of_work, place_of_work_value):
        self.place_of_work = place_of_work
        self.place_of_work_value = place_of_work_value
        logger.info("Место работы установлено")

    def set_other_info(self, other_info):
        self.other_info = other_info
        logger.info("Другая информация установлена")

def employee_to_dict(empl: Employee) -> dict:
    if not isinstance(empl.image, np.ndarray):
        raise ValueError("empl.image должен быть numpy.ndarray (grayscale 224×224)")

    if empl.image.shape != (224, 224):
        raise ValueError(f"Ожидается форма (224, 224), получено {empl.image.shape}")

    if empl.image.dtype != np.uint8:
        raise ValueError(f"Ожидается dtype uint8, получено {empl.image.dtype}")

    # Самое эффективное сжатие для маленьких grayscale изображений
    compressed = zlib.compress(empl.image.tobytes(), level=9)

    if empl.patronymic == "-":
        empl.patronymic = ""
        empl.full_name = empl.surname + " " + empl.name
        
    employee_dict = {
        "_id": ObjectId(),
        "name": empl.name,
        "surname": empl.surname,
        "patronymic": empl.patronymic,
        "full_name": empl.full_name,
        "title": empl.title,
        "access_level": empl.access_level,
        "contacts": empl.contacts,
        "hiring_date": empl.hiring_date,
        "id_index": empl.id_index,
        "salary": empl.salary,

        # Место работы — структурированно (рекомендую так, а не динамический ключ)
        "workplace": {
            "type": getattr(empl, "place_of_work", None),
            "value": getattr(empl, "place_of_work_value", None)
        },

        # Изображение
        "face_image": Binary(compressed),
        "image_metadata": {
            "shape": list(empl.image.shape),      # [224, 224]
            "dtype": str(empl.image.dtype),        # 'uint8'
            "compression": "zlib",
            "original_bytes": empl.image.nbytes   # 50176
        }
    }

    # Дополнительные поля
    if hasattr(empl, "other_info") and isinstance(empl.other_info, dict):
        employee_dict.update(empl.other_info)

    
    return employee_dict 

def get_employee_image(doc: dict) -> np.ndarray | None:
    if "face_image" not in doc:
        return None

    compressed = doc["face_image"]
    if not isinstance(compressed, Binary):
        return None

    decompressed = zlib.decompress(compressed)
    shape = tuple(doc["image_metadata"]["shape"])
    dtype = np.dtype(doc["image_metadata"]["dtype"])

    img = np.frombuffer(decompressed, dtype=dtype).reshape(shape)
    return img

