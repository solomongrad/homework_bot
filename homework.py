from http import HTTPStatus
import logging
import logging.handlers
import os
import sys
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

from exceptions import (EmptyAnswerFromAPIException,
                        HomeworkStatusException,
                        TokenUnvaibleException,
                        InvalidResponseCodeException)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

logging.basicConfig(
    filename=__file__ + '.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(lineno)d, %(message)s,',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)

logger.addHandler(logging.FileHandler(__file__ + '.log'))

logger.addHandler(logging.StreamHandler(sys.stdout))

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PAYLOAD = {'from_date': 1549962000}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Функция которая проверяет доступность переменных окружения."""
    name_token_tuple = (
        ('Токен Яндекс Практикума недоступен', PRACTICUM_TOKEN),
        ('Токен Телеграмма недоступен', TELEGRAM_TOKEN),
        ('ID чата в телеграмме отсутствует', TELEGRAM_CHAT_ID)
    )
    bool_variable = True
    for text, token in name_token_tuple:
        if not token:
            logger.critical(text)
            bool_variable = False
    if bool_variable is False:
        raise TokenUnvaibleException('Один из токенов недействителен')


def get_api_answer(timestamp):
    """
    Функция которая выполняет запрос к указанному эндпоинту.

    timestamp - временной промежуток, за который нужны домашние работы
    """
    request_data = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': timestamp
    }
    try:
        logger.info('Совершаю запрос к {url} с аргументами: headers={headers},'
                    ' params={params} '.format(**request_data))
        response = requests.get(**request_data)
    except requests.RequestException:
        raise ConnectionError(
            'ошибка соединения с сайтом по '
            'адресу {url}'.format(**request_data)
        )
    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseCodeException(
            f'Эндпоинт {response.url} недоступен. '
            f'Код ответа: {response.status_code}.'
            f'Причина: {response.reason}'
            f'Текст: {response.text}'
        )
    return response.json()


def check_response(response):
    """
    Функция которая проверяет ответ API.

    параметр response - запрос, который нужно проверить
    """
    if not isinstance(response, dict):
        raise TypeError('Тип данных не соответствует ожидаемым. \n'
                        "Ожидался: <class 'dict'> \n"
                        f'Получили: {type(response)}')
    if 'homeworks' not in response:
        raise EmptyAnswerFromAPIException(
            'Отсутствие ожидаемых ключей в ответе API.'
        )
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Тип данных не соответствует ожидаемым.')
    return homeworks


def parse_status(homework: dict):
    """
    Функция, которая извлекает статус домашней работы из информации о ней.

    параметр homework - объект домашней работы
    """
    if 'homework_name' not in homework:
        raise KeyError
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise HomeworkStatusException('Отсутствует ключ "status".')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusException(
            'Ключ "status" вернул неожиданное значение.'
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, text):
    """Функция которая отправляет сообщение в телеграмм.

    параметры:
    bot - объект бота, который должен отправить сообщение
    text - текст сообщения
    """
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as error:
        logger.error(f'Собщение не отправлено. Ошибка: {error}')
        return False
    logger.debug(f'Было отправлено сообщение: {text}')
    return True


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('Список домашних работ пуст')
                continue
            current_message = parse_status(homeworks[0])
            if current_message != previous_message and (
                send_message(bot, current_message)
            ):
                previous_message = current_message
                timestamp = response.get('current_date', timestamp)
            else:
                logger.debug('В ответе отсутствуют новые статусы')

        except Exception as error:
            text = f'Сбой в работе программы: {error}'
            logger.error(text)
            if text != previous_message and send_message(bot, text):
                previous_message = current_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
