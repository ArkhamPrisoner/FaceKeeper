import cv2
import logging

logger = logging.getLogger(__name__)


class Camera:
    def __init__(self):
        self.cap = None
        self.source = None
        self.rotation = 0  # 0, 90, 180, 270

        # Проверка локальной камеры
        test_cap = cv2.VideoCapture(0)
        if test_cap.isOpened():
            test_cap.release()
            self.source = 0
            logger.info("Локальная камера доступна")
            return

        test_cap.release()
        logger.error("Не удалось открыть локальную камеру")

        # Проверка IP камеры
        http = input("Введите http > ").strip()
        self.source = f"http://{http}/video"

        test_cap = cv2.VideoCapture(self.source)
        if not test_cap.isOpened():
            test_cap.release()
            raise Exception("Не удалось подключиться к IP камере")

        test_cap.release()
        logger.info("IP камера доступна")

    def _open(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.source)

            if not self.cap.isOpened():
                raise Exception("Не удалось открыть камеру")

            logger.info("Камера запущена")

    def _rotate_frame(self, frame):
        """Поворот кадра"""
        if self.rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def take_photo(self):
        self._open()

        print("""
[s] — сделать снимок
[q] — выход
[r] — повернуть на 90° вправо
[l] — повернуть на 90° влево
[f] — перевернуть (180°)
""")

        while True:
            ret, frame = self.cap.read()

            if not ret:
                logger.error("Ошибка чтения кадра")
                self.release()
                raise Exception("Ошибка чтения кадра")

            # применяем поворот
            frame = self._rotate_frame(frame)

            cv2.imshow("Camera", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                self.release()
                return None

            elif key == ord('s'):
                logger.info("Снимок сделан")
                result = frame.copy()
                self.release()
                return result

            elif key == ord('r'):
                self.rotation = (self.rotation + 90) % 360
                logger.info(f"Поворот: {self.rotation}")

            elif key == ord('l'):
                self.rotation = (self.rotation - 90) % 360
                logger.info(f"Поворот: {self.rotation}")

            elif key == ord('f'):
                self.rotation = (self.rotation + 180) % 360
                logger.info(f"Поворот: {self.rotation}")

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        cv2.destroyAllWindows()
        logger.info("Камера освобождена")