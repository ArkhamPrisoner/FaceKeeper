import pymongo
from pymongo import MongoClient, ASCENDING
import datetime
import logging
from employee import Employee, employee_to_dict
import numpy as np
from user import User
from bson import ObjectId
import ipinfo

logger = logging.getLogger(__name__)

class MongoManager:
    """Класс для работы с MongoDB"""
    
    def __init__(self, uri="mongodb://localhost:27017/", db_name="employee_db"):
        """
        Инициализация подключения к MongoDB
        
        Args:
            uri: строка подключения
            db_name: имя базы данных
        """
        access_token = 'e8943b3e104ea1'
        self.handler = ipinfo.getHandler(access_token)
        self.client = MongoClient(uri)
        logger.info(f"Клиент mongodb создан по {uri}")

        self.db = self.client[db_name]
        logger.info(f"Клиент mongodb подключен к БД {db_name}")
        if "auth_log" not in self.db.list_collection_names():
            self.db.create_collection(
                "auth_log",
                capped=True,
                size=1024 * 1024,   # 1MB
                max=1000
            )
        logger.info("Capped collection auth_log создана")
        # Коллекции
        self.employee = self.db['employee']
        logger.info(f"Коллекция employee найдена")
        self.auth_log = self.db['auth_log']
        logger.info(f"Коллекция auth_log найдена")
        self.work_place = self.db["work_place"]
        # Создаём индексы
        self._create_indexes()

    
    def _create_indexes(self):
        """Создаёт индексы для быстрого поиска"""
        # Индекс для employee
        self.employee.create_index([("full_name", ASCENDING)])
        logger.info("Индексы MongoDB созданы")
        self.employee.create_index([("full_name", ASCENDING)])
        self.work_place.create_index([("name", ASCENDING), ("building", ASCENDING)], unique=True)
        logger.info("Индексы MongoDB созданы")
    
    def add_employee(self, person: Employee):
        """
        Добавляет информацию о лице
        
        Args:
            face_data: dict с полями:
                - _id: уникальный ID
                - name: имя человека
                - surname: фамилия человека
                - patronymic: отчество человека
                - full_name: Фамилия И.О
                - title: должность
                - access_level: уровень доступа
                - image_path: вырезанное лицо
                - Hiring_date: дата найма
                - contacts["email", "phone"]: Контактная информация
                - cabinet/building/car ...: место нахождения работника
                - other: другая информация

        Returns:
            inserted_id
        """
        person_dict = employee_to_dict(person)
        
        result = self.employee.insert_one(person_dict)

        logger.info(f"{person.full_name}: добавлен")

        return person_dict.get("_id")
    
    def find_by_full_name(self, full_name):
        results = list(self.employee.find(
            {"full_name": full_name},
            {
                "_id": 1,
                "full_name": 1,
                "title": 1,
                "access_level": 1,
            }
        ))
        return results
    
    def find_by_id(self, employee_id: ObjectId):
        find_result = self.employee.find_one({"_id":  employee_id})
        return find_result
    
    def dell_by_id(self, face_id):
        self.employee.delete_one({"_id": face_id})
    
    def log_in(self, indices):
        details = self.handler.getDetails()  
        employee_data = self.employee.find_one(
            {"id_index": int(indices)},
            {
                "_id": 1,
                "full_name": 1,
                "access_level": 1,
            }
        )
        user = User(employee_data.get("_id"), employee_data.get("full_name"),employee_data.get("access_level"))
        # Добавляем временную метку
        login_record = {
            "employee_id": employee_data.get("_id"),
            "full_name": employee_data.get("full_name"),
            "login_time": datetime.datetime.now(),
            "status": "login",
            "country": details.country_name,
            "city": details.city,
            "location": details.loc,
            "provider": details.org,
            "ip": details.ip
        }
        self.auth_log.insert_one(login_record)
        logger.info(f"Запись о входе добавлена для {employee_data.get('full_name')} в {login_record['login_time']}")
        return (True, user)
    
    def log_out(self, user: User):
        logout_record = {
            "employee_id": user.bd_id[0],
            "full_name": user.fullname[0],
            "login_time": datetime.datetime.now(),
            "status": "logout"
        }
        self.auth_log.insert_one(logout_record)
        logger.info(f"Запись о выходе добавлена для {user.fullname} в {logout_record['login_time']}")

    def agg_avg_salary_by_title(self):
        pipeline = [
        {"$group": {
            "_id": "$title",  # Группируем по должности
            "average_salary": {"$avg": "$salary"},
            "count": {"$sum": 1}  # Сколько сотрудников
        }},
        {"$sort": {"average_salary": -1}}  # Сортировка по убыванию
        ]
        results = list(self.employee.aggregate(pipeline))
        return results
    
    def sum_employee_by_title(self):
        pipeline = [
        {"$group": {
            "_id": "$title",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
        results = list(self.employee.aggregate(pipeline))
        return results

    def agg_hired_by_date(self):
        """Количество нанятых по годам и месяцам"""
        pipeline = [
            {"$group": {
                "_id": {
                    "year": {"$year": "$hiring_date"},
                    "month": {"$month": "$hiring_date"}
                },
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id.year": -1, "_id.month": -1}}
        ]
        results = list(self.employee.aggregate(pipeline))
        return results