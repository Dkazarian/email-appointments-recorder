class ParserError(Exception):
    pass

class Parser:
    def __init__(self, ia_client: object) -> None:
        raise NotImplementedError
    def parse_all(self, mails: list[object]) -> object:
        raise NotImplementedError
