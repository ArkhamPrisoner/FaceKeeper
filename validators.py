import re


class Validator:

    @staticmethod
    def email(email):
        return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

    @staticmethod
    def phone(phone):
        return re.match(r'^(\+7|8)?\d{10}$', phone)

    @staticmethod
    def input_contacts():
        while True:
            email = input("Email: ")
            if Validator.email(email):
                break

        while True:
            phone = input("Phone: ")
            if Validator.phone(phone):
                break

        return {"email": email, "phone": phone}

    @staticmethod
    def input_access_level():
        while True:
            try:
                level = int(input("Access level (0-5): "))
                if 0 <= level <= 5:
                    return level
            except:
                pass
    
    @staticmethod
    def input_salary():
        while True:
            try:
                salary = int(input("Заработок: "))
                return salary
            except:
                pass