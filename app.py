import logging
import os
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from face_embedding import FaceEmbedding
from FAISS_initial import FaissManager
from mongodb_acces import MongoManager
from YOLO_cropping import get_model, image_preprocessing
from employee import Employee
from camera import Camera

from validators import Validator
from place_manager import PlaceOfWorkManager


class FaceAccessApp:

    def __init__(self):
        self.logger = self._init_logger()

        self.model = get_model("arnabdhar/YOLOv8-Face-Detection")
        self.embedder = FaceEmbedding()
        self.index = FaissManager()
        self.db = MongoManager()

        self.place_manager = PlaceOfWorkManager(self.logger)

    def _init_logger(self):
        os.makedirs('logs', exist_ok=True)

        log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)

    def _capture_embedding(self):
        camera = Camera()
        img = camera.take_photo()
        if img is None:
            return None, None

        cropped = image_preprocessing(img, self.model)
        if cropped is None:
            return None, None

        embedding = self.embedder.get_embedding(img)
        if embedding is None:
            return None, None

        return embedding, cropped

    def login_user(self):
        embedding, _ = self._capture_embedding()
        if embedding is None:
            return False, None

        emb = self.index._prepare_embedding(embedding)

        if self.index.index.ntotal == 0:
            return False, None

        scores, indices = self.index.index.search(emb, 1)

        if scores[0][0] > 0.7:
            (ok, user) = self.db.log_in(indices[0][0])
            self.user = user
            return ok

        self.logger.info('Face not found')
        return False, None

    def logout_user(self, user):
        self.db.log_out(user)


    def add_employee(self):
        embedding, cropped = self._capture_embedding()
        if embedding is None:
            return

        if self.index.index.ntotal > 0:
            score, indice = self.index.search(embedding, 1)
            if score > 0.7:
                print(f"Лицо уже существует")
                return None
        id_index = self.index.add_embedding(embedding)

        if id_index is None:
            print("Лицо уже существует")
            return

        # Внутри этой функции вызовется наш новый список выбора мест
        employee = self._collect_employee_data(cropped, id_index)
        
        # Сохраняем сотрудника в MongoDB и получаем его сгенерированный ObjectId
        employee_id = self.db.add_employee(employee)
        self.index.save()

        # Если место было успешно выбрано, связываем документы в базе данных
        if hasattr(self, "_selected_workplace_id") and self._selected_workplace_id and employee_id:
            try:
                self.db.work_place.update_one(
                    {"_id": self._selected_workplace_id},
                    {"$addToSet": {"workers": employee_id}}
                )
                print("Сотрудник успешно привязан к списку работников выбранной зоны.")
            except Exception as e:
                self.logger.error(f"Ошибка при синхронизации рабочего места: {e}")
            finally:
                # Очищаем временную переменную
                self._selected_workplace_id = None

    def _collect_employee_data(self, image, id_index):

        name = input("Имя: ").strip()
        surname = input("Фамилия: ").strip()
        patronymic = input("Отчество: ").strip()
        title = input("Должность: ").strip()
        salary = Validator.input_salary()
        access_level = Validator.input_access_level()
        contacts = Validator.input_contacts()
        employee = Employee(
            name=name,
            surname=surname,
            patronymic=patronymic,
            title=title,
            access_level=access_level,
            image=image,
            contacts=contacts,
            id_index = id_index,
            salary= salary
        )

        self._input_place_of_work(employee)
        self._input_other(employee)

        return employee

    def _input_place_of_work(self, employee):
        """Выбор рабочего места из существующих в базе данных документов work_place"""
        # Инициализируем временную переменную для связи документов
        self._selected_workplace_id = None
        
        # Извлекаем все доступные рабочие места из базы данных
        workplaces = list(self.db.work_place.find())
        
        if not workplaces:
            print("\n[Предупреждение] В базе данных нет созданных рабочих мест.")
            print("Сотрудник будет зарегистрирован без привязки к конкретной зоне.")
            employee.set_place_of_work(None, None)
            return

        print("\n--- Доступные рабочие места ---")
        for idx, wp in enumerate(workplaces, 1):
            req_level = wp.get("required_access_level", 0)
            capacity = wp.get("capacity", 10)
            current_workers_count = len(wp.get("workers", []))
            
            # Формируем маркеры ограничений
            status_marker = ""
            if employee.access_level < req_level:
                status_marker += " (Недостаточный уровень доступа)"
            if current_workers_count >= capacity:
                status_marker += " (Нет свободных мест)"
                
            print(f"{idx} - {wp['name']} [{wp['type']}] | "
                  f"Корпус: {wp['building']}, Этаж: {wp['floor']} | "
                  f"Занято: {current_workers_count}/{capacity} | "
                  f"Мин. уровень: {req_level}{status_marker}")

        while True:
            choice = input("\nВыберите номер рабочего места (или нажмите Enter, чтобы пропустить): ").strip()
            if not choice:
                employee.set_place_of_work(None, None)
                print("Привязка к рабочему месту пропущена.")
                break
                
            try:
                selected_idx = int(choice) - 1
                if 0 <= selected_idx < len(workplaces):
                    selected_wp = workplaces[selected_idx]
                    
                    # 1. Проверка уровня доступа сотрудника требованиям зоны
                    if employee.access_level < selected_wp.get("required_access_level", 0):
                        print(f"Ошибка: Уровень доступа сотрудника ({employee.access_level}) "
                              f"ниже требуемого для этой зоны ({selected_wp.get('required_access_level', 0)}).")
                        continue
                    
                    # 2. Проверка заполненности помещения
                    if len(selected_wp.get("workers", [])) >= selected_wp.get("capacity", 10):
                        print(f"Ошибка: Зона '{selected_wp['name']}' переполнена.")
                        continue

                    # Записываем структурированные данные в объект сотрудника
                    employee.set_place_of_work(selected_wp["type"], selected_wp["name"])
                    
                    # Запоминаем ID выбранной записи для финальной транзакции/обновления
                    self._selected_workplace_id = selected_wp["_id"]
                    print(f"Успешно выбрано место: {selected_wp['name']}")
                    break
                else:
                    print("Неверный номер. Пожалуйста, выберите число из списка.")
            except ValueError:
                print("Введите корректное число.")

    def _input_other(self, employee):
        other = {}

        while True:
            key = input("Ключ: ")
            if not key:
                break
            value = input("Значение: ")
            other[key] = value

        if other:
            employee.set_other_info(other)

    def search_by_full_name(self):
        full_name = input("Введите ФИО: ")
        results = self.db.find_by_full_name(full_name)

        print(f"Найдено {len(results)}")
        for emp in results:
            print(emp)

    def dell_employee(self):
        print("Введите id пользователя для удаление")
        employee_id = input("> ").strip()
        try:
            oid = ObjectId(employee_id)
        except InvalidId:
            return None
        employee = self.db.find_by_id(oid)
        if employee is None:
            print("Пользователь не найден")
            self.logger.info(f"Пользователя _id: {employee_id}, невозможно удалить, так как его не существует")
            return None
        self.db.dell_by_id(employee.get("_id"))
        self.logger.info(f"Пользователь {employee.get('full_name')} удален из MongoDB")
        self.index.remove_embedding(employee.get("id_index"))

    def add_workplace(self):
        """Интерактивное создание и сохранение рабочего места через консоль"""
        print("\n--- Регистрация нового рабочего места / зоны доступа ---")
        name = input("Название/Номер (например, Кабинет 301, Серверная А): ").strip()
        wp_type = input("Тип зоны (cabinet, office, laboratory, server_room): ").strip().lower()
        building = input("Корпус/Здание: ").strip()
        
        try:
            floor = int(input("Этаж: "))
            req_access = int(input("Минимальный уровень доступа для входа (0-5): "))
            capacity = int(input("Максимальная вместимость (кол-во человек): "))
        except ValueError:
            print("Ошибка: Этаж, уровень доступа и вместимость должны быть целыми числами.")
            return

        description = input("Описание помещения (опционально): ").strip()
        equipment_raw = input("Оборудование (через запятую, опционально): ").strip()
        equipment = [e.strip() for e in equipment_raw.split(",")] if equipment_raw else []

        from work_place import Work_place  # Локальный импорт во избежание цикличности
        
        try:
            new_wp = Work_place(
                name=name,
                workplace_type=wp_type,
                building=building,
                floor=floor,
                required_access_level=req_access,
                capacity=capacity,
                description=description,
                equipment=equipment
            )
            new_wp.save()
        except Exception as e:
            self.logger.error(f"Не удалось сохранить рабочее место: {e}")
            print("Произошла ошибка при сохранении объекта в базу данных.")

    def agg_menu(self):
        while True:
            print("Введите способ агрегации:")
            print("1 - средняя зарплата по отделам")
            print("2 - кол-во сотрудников по должностям")
            print("3 - кол-во нанятых по годам и месяцам")
            print("4 - выход")
            try:
                agg_val = int(input("> "))
                if agg_val  < 1 and agg_val > 4:
                    print("Выберите доступные значения")
                    continue
            except:
                print("Введите число")
                continue
            match agg_val:
                case 1:
                    print(self.db.agg_avg_salary_by_title())
                case 2:
                    print(self.db.sum_employee_by_title())
                case 3:
                    print(self.db.agg_hired_by_date())
                case 4:
                    break
                case _:
                    print("Неизвестная команда")

    def _show_menu(self):
        match (self.user.access_level):
            case 0:
                print("У вас нет никаких прав")
                print("q - Выйти")
                cmd = input("> ")
                match cmd:
                    case 'q':
                        print("Выход из приложения")
                        self.db.log_out(self.user)
                        return True
                    case _:
                        print("Неизвестная команда")
                        return False
            case 1:
                print("1 - Найти по ФИО")
                print("q - Выйти")
                cmd = input("> ")
                match cmd:
                    case 'q':
                        print("Выход из приложения")
                        self.db.log_out(self.user)
                        return True
                    case '1':
                        self.search_by_full_name()
                        return False
                    case _:
                        print("Неизвестная команда")
                        return False
            case 2:
                print("1 - Найти по ФИО")
                print("2 - Агрегация данных")
                print("q - Выйти")
                cmd = input("> ")
                match cmd:
                    case 'q':
                        print("Выход из приложения")
                        self.db.log_out(self.user)
                        return True
                    case '1':
                        self.search_by_full_name()
                        return False
                    case '2':
                        self.agg_menu()
                    case _:
                        print("Неизвестная команда")
                        return False
            case 3:
                print("1 - Найти по ФИО")
                print("q - Выйти")
                cmd = input("> ")
                match cmd:
                    case 'q':
                        print("Выход из приложения")
                        self.db.log_out(self.user)
                        return True
                    case '1':
                        self.search_by_full_name()
                        return False
                    case '2':
                        self.agg_menu()
                    case _:
                        print("Неизвестная команда")
                        return False
            case 4:
                print("1 - Найти по ФИО")
                print("2 - Агрегация данных")
                print("3 - Добавить пользователя")
                print("4 - Добавить рабочее место")  # Добавлено
                print("q - Выйти")
                cmd = input("> ")
                match cmd:
                    case 'q':
                        print("Выход из приложения")
                        self.db.log_out(self.user)
                        return True
                    case '1':
                        self.search_by_full_name()
                        return False
                    case '2':
                        self.agg_menu()
                        return False
                    case '3':
                        self.add_employee()
                        return False
                    case '4':
                        self.add_workplace()  # Добавлено
                        return False
                    case _:
                        print("Неизвестная команда")
                        return False
            case 5:
                print("1 - Найти по ФИО")
                print("2 - Агрегация данных")
                print("3 - Добавить пользователя")
                print("4 - Удалить пользователя")
                print("5 - Добавить рабочее место")  # Добавлено
                print("q - Выйти")
                cmd = input("> ")
                match cmd:
                    case 'q':
                        print("Выход из приложения")
                        self.db.log_out(self.user)
                        return True
                    case '1':
                        self.search_by_full_name()
                        return False
                    case '2':
                        self.agg_menu()
                        return False
                    case '3':
                        self.add_employee()
                        return False
                    case '4':
                        self.dell_employee()
                        return False
                    case '5':
                        self.add_workplace()  # Добавлено
                        return False
                    case _:
                        print("Неизвестная команда")
                        return False             

    def run(self):
        ok = self.login_user()
        if not ok:
            print("Access denied")
            return

        print(f"Hello {self.user.fullname}")

        while not self._show_menu():
            pass