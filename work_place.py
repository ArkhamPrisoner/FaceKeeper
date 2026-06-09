import datetime
from bson import ObjectId
from mongodb_acces import MongoManager

class Work_place:
    """Класс для управления рабочими местами и зонами доступа"""
    
    def __init__(self, name: str, workplace_type: str, building: str, floor: int, 
                 required_access_level: int, capacity: int = 10, description: str = "", equipment=None):
        """
        Args:
            name: Уникальное имя/номер помещения (например, 'Кабинет 301', 'Серверная А')
            workplace_type: Тип зоны (cabinet, laboratory, server_room, office)
            building: Корпус или здание
            floor: Этаж
            required_access_level: Минимальный уровень доступа (0-5) для входа в эту зону
            capacity: Максимальное количество одновременно закрепленных сотрудников
            description: Краткое описание назначения помещения
            equipment: Список находящегося там оборудования/инфраструктуры
        """
        self.db = MongoManager()
        self.name = name
        self.type = workplace_type
        self.building = building
        self.floor = floor
        self.required_access_level = required_access_level
        self.capacity = capacity
        self.description = description
        self.equipment = equipment if equipment else []
        self.workers = []
        self.created_at = datetime.datetime.now()
        
    def to_dict(self) -> dict:
        """Превращает объект в документ для MongoDB"""
        return {
            "name": self.name,
            "type": self.type,
            "building": self.building,
            "floor": self.floor,
            "required_access_level": self.required_access_level,
            "capacity": self.capacity,
            "description": self.description,
            "equipment": self.equipment,
            "workers": self.workers,
            "created_at": self.created_at
        }
        
    def save(self):
        """Сохраняет новое рабочее место в коллекцию work_place с проверкой на дубликаты"""
        exists = self.db.work_place.find_one({"name": self.name, "building": self.building})
        if exists:
            print(f"Рабочее место '{self.name}' в корпусе '{self.building}' уже существует.")
            return exists["_id"]
            
        wp_dict = self.to_dict()
        result = self.db.work_place.insert_one(wp_dict)
        print(f"Рабочее место '{self.name}' успешно добавлено в базу данных.")
        return result.inserted_id
        
    def push_employee(self, worker_id: ObjectId):
        """Привязка сотрудника к рабочему месту в рамках ACID транзакции"""
        # Ищем актуальные данные о рабочем месте
        wp = self.db.work_place.find_one({"name": self.name})
        if not wp:
            print("Рабочее место не найдено в базе данных.")
            return False

        # Проверяем лимит заполненности помещения
        if len(wp.get("workers", [])) >= wp.get("capacity", 10):
            print(f"Невозможно распределить сотрудника: достигнут лимит вместимости зоны {self.name}.")
            return False

        with self.db.client.start_session() as session:
            with session.start_transaction():
                # Ищем сотрудника
                employee = self.db.employee.find_one({"_id": worker_id}, session=session)
                if employee is None:
                    print(f"Сотрудник с ID {worker_id} не найден.")
                    session.abort_transaction()
                    return False
                
                # Проверяем, не привязан ли уже сотрудник к какому-либо месту
                current_workplace = employee.get("workplace", {})
                if current_workplace.get("value") is not None:
                    print(f"Работник уже привязан к зоне: {current_workplace.get('value')}")
                    session.abort_transaction()
                    return False

                # Проверяем соответствие уровней безопасности
                if employee.get("access_level", 0) < wp.get("required_access_level", 0):
                    print(f"Отказ: Уровень доступа сотрудника ({employee.get('access_level')}) "
                          f"ниже требуемого для зоны {self.name} ({wp.get('required_access_level')}).")
                    session.abort_transaction()
                    return False

                # Обновляем документ сотрудника (привязываем рабочее место)
                self.db.employee.update_one(
                    {"_id": worker_id},
                    {"$set": {
                        "workplace.type": wp["type"],
                        "workplace.value": wp["name"]
                    }},
                    session=session
                )
                
                # Добавляем ID сотрудника в массив работников этой зоны
                self.db.work_place.update_one(
                    {"_id": wp["_id"]},
                    {"$addToSet": {"workers": worker_id}},
                    session=session
                )
                
                print(f"Сотрудник {employee.get('full_name')} успешно распределен в зону {self.name}.")
                return True