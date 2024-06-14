import logging
import logging.handlers
import os
import sys
import time

from dotenv import load_dotenv
from http import HTTPStatus
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
    format='%(asctime)s, %(levelname)s, %(lineno)d, %(message)s,'
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
            logging.critical(text)
            bool_variable = False
    if bool_variable is False:
        raise TokenUnvaibleException('Один из токенов недействителен')

    # if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN:
    #     logging.critical('Один из токенов недействителен')
    #     sys.exit('Токен Яндекс Практикума недействителен')


def get_api_answer(timestamp):
    """
    Функция которая выполняет запрос к указанному эндпоинту.

    timestamp - временной промежуток, за который нужны домашние работы
    """
    arguments_dict = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': timestamp
    }
    try:
        logging.info(f"Совершаю запрос к {arguments_dict['url']} "
                     f"с аргументами: headers={arguments_dict['headers']}, "
                     f"params={arguments_dict['params']} "
                     f"Словарь - {arguments_dict}")
        response = requests.get(arguments_dict['url'],
                                headers=arguments_dict['headers'],
                                params=arguments_dict['params'])
    except requests.RequestException:
        raise ConnectionError(
            f'{arguments_dict}, \nошибка соединения с сервером'
        )
    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseCodeException(
            f'Эндпоинт {arguments_dict["url"]} недоступен. '
            'Код ответа: {response.status_code}.'
        )
    return response.json()


def check_response(response):
    """
    Функция которая проверяет ответ API.

    параметр response - запрос, который нужно проверить
    """
    if not isinstance(response, dict):
        raise TypeError('Тип данных не соответствует ожидаемым.')
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
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise HomeworkStatusException(
            'Ключ "status" вернул неожиданное значение.'
        )
    verdict = HOMEWORK_VERDICTS[homework['status']]
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
        logging.error(f'Собщение не отправлено. Ошибка: {error}')
    logging.debug(f'Было отправлено сообщение: {text}')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_status = ''
    last_string = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Список домашних работ пуст')
                continue
            current_status = parse_status(homeworks[0])
            if current_status != previous_status:
                send_message(bot, current_status)
                previous_status = current_status
            else:
                logging.debug('В ответе отсутствуют новые статусы')

        except Exception as error:
            current_string = f'Сбой в работе программы: {error}'
            logging.error(current_string)
            if current_string != last_string:
                last_string = current_string
                send_message(bot, current_string)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
