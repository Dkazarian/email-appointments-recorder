class DatabaseError(Exception):
    pass

class DatabaseClient:
    def __init__(self) -> None:
        raise NotImplementedError
    def add(self, extracted: object) -> None:
        raise NotImplementedError
