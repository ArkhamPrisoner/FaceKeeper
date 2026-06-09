from employee import Employee
from mongodb_acces import MongoManager
from bson import ObjectId

class WorkPlace:
    def __init__(self, name: str):
        self.db = MongoManager()
        self.name = name
        self.collection = self.db.db['work_place']  # Коллекция для рабочих мест
    
    def push_employee(self, workers):
        """
        Добавление сотрудников на рабочее место
        
        Args:
            workers: список ID сотрудников или один ID
        """
        # Приводим к списку, если передан один ID
        if not isinstance(workers, list):
            workers = [workers]
        
        with self.db.client.start_session() as session:
            try:
                session.start_transaction()
                
                # Проверяем существование рабочего места, создаем если нет
                work_place = self.collection.find_one(
                    {"name": self.name},
                    session=session
                )
                
                if not work_place:
                    # Создаем новое рабочее место
                    result = self.collection.insert_one(
                        {"name": self.name, "workers": []},
                        session=session
                    )
                    work_place_id = result.inserted_id
                else:
                    work_place_id = work_place['_id']
                
                added_workers = []
                failed_workers = []
                
                for worker_id in workers:
                    # Проверяем, существует ли сотрудник и не привязан ли уже к месту
                    find_worker = self.db.employee.find_one(
                        {
                            "_id": ObjectId(worker_id) if isinstance(worker_id, str) else worker_id,
                            "work_place": {"$exists": False}
                        },
                        {"_id": 1, "full_name": 1},
                        session=session
                    )
                    
                    if find_worker is None:
                        print(f"❌ Работник {worker_id} уже где-то работает или не существует")
                        failed_workers.append(worker_id)
                        continue
                    
                    # Обновляем сотрудника - добавляем место работы
                    self.db.employee.update_one(
                        {"_id": find_worker['_id']},
                        {"$set": {"work_place": self.name}},
                        session=session
                    )
                    
                    # Добавляем сотрудника в список рабочих мест
                    self.collection.update_one(
                        {"_id": work_place_id},
                        {"$addToSet": {"workers": find_worker['_id']}},  # addToSet, а не addToset
                        session=session
                    )
                    
                    added_workers.append({
                        "id": find_worker['_id'],
                        "name": find_worker['full_name']
                    })
                
                if failed_workers and not added_workers:
                    # Если не добавили ни одного - откатываем
                    session.abort_transaction()
                    print("❌ Транзакция откачена: не добавлен ни один сотрудник")
                    return False
                
                session.commit_transaction()
                print(f"✅ Добавлено сотрудников: {len(added_workers)}")
                print(f"❌ Не добавлено: {len(failed_workers)}")
                return True
                
            except Exception as e:
                session.abort_transaction()
                print(f"❌ Ошибка транзакции: {e}")
                return False