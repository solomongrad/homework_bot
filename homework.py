import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from http import HTTPStatus
from telebot import TeleBot, types

from exceptions import (UnavailableEndpointException,
                        ResponseErrorException,
                        HomeworkStatusException)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(message)s,'
)

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
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN:
        logging.critical('Один из токенов недействителен')
        sys.exit('Токен Яндекс Практикума недействителен')


def get_api_answer(timestamp):
    """
    Функция которая выполняет запрос к указанному эндпоинту.

    timestamp - временной промежуток, за который нужны домашние работы
    """
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
    except requests.RequestException:
        logging.error('Неизвестная ошибка')
    if response.status_code == HTTPStatus.OK:
        return response.json()
    logging.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
                  'Код ответа API: {response.status_code}')
    raise UnavailableEndpointException(f'Эндпоинт {ENDPOINT} недоступен.')


def check_response(response):
    """
    Функция которая проверяет ответ API.

    параметр response - запрос, который нужно проверить
    """
    if not isinstance(response, dict):
        raise TypeError
    if 'homeworks' in response and (
        'current_date' in response
    ):
        if not isinstance(response['homeworks'], list):
            raise TypeError
        response['homeworks'][0]
    else:
        logging.error('Произошла ошибка: Отсутствие ожидаемых '
                      'ключей в ответе API')
        raise ResponseErrorException


def parse_status(homework: dict):
    """
    Функция, которая извлекает статус домашней работы из информации о ней.

    параметр homework - объект домашней работы
    """
    if 'homework_name' not in homework.keys():
        raise KeyError
    homework_name = homework['homework_name']
    if 'status' not in homework.keys() or (
        homework['status'] not in HOMEWORK_VERDICTS.keys()
    ):
        raise HomeworkStatusException
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
        logging.debug(f'Было отправлено сообщение: {text}')
    except Exception as error:
        logging.error(f'Собщение не отправлено. Ошибка: {error}')


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_status = None

    while True:
        check_tokens()
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if parse_status(response['homeworks'][0]) != previous_status:
                previous_status = response['homeworks'][0]['status']
                send_message(bot, HOMEWORK_VERDICTS[previous_status])
            else:
                logging.debug('В ответе отсутствуют новые статусы')

        except UnavailableEndpointException as error:
            text = f'Сбой в работе программы: {error}'
            send_message(bot, text)
        except ResponseErrorException as error:
            text = f'Сбой в работе программы: {error}'
            send_message(bot, text)
        except KeyError as error:
            text = f'Сбой в работе программы: {error}'
            logging.error(text)
            send_message(bot, text)
        except IndexError:
            text = 'Список домашних заданий пуст!'
            logging.error(text)
            send_message(bot, text)
        except TypeError as error:
            text = f'Сбой в работе программы: {error}'
            logging.error(text)
            send_message(bot, text)
        except HomeworkStatusException as error:
            text = f'Сбой в работе программы: {error}'
            logging.error(text)
            send_message(bot, text)
        except requests.RequestException as error:
            text = f'Сбой в работе программы: {error}'
            logging.error(text)
            send_message(bot, text)
        time.sleep(RETRY_PERIOD)
        bot.polling()


if __name__ == '__main__':
    main()
