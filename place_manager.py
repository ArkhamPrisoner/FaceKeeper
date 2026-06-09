class PlaceOfWorkManager:

    def __init__(self, logger):
        self.logger = logger
        self.file = 'place_of_work.txt'
        self.records = self._load()

    def _load(self):
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                return f.read().split()
        except:
            return []

    def update(self, place_type):
        if place_type not in self.records:
            self.records.append(place_type)
            with open(self.file, 'w', encoding='utf-8') as f:
                f.write(' '.join(self.records))

            self.logger.info(f"New place type: {place_type}")