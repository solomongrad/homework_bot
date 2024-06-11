class UnavailableEndpointException(Exception):
    def __init__(self, message='Эндпоинт недоступен.'):
        super().__init__(message)


class ResponseErrorException(Exception):
    def __init__(self, message='Произошла ошибка: Отсутствие ожидаемых '
                 'ключей в ответе API'):
        super().__init__(message)


class HomeworkStatusException(Exception):
    def __init__(self,
                 message='Статус домашней работы не '
                 'соответствует ожидаемому.'):
        super().__init__(message)
