import logging
import os
import sys

import requests
from telegram import Bot

from http import HTTPStatus
import time

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        level=logging.INFO,
        filename='main.log',
        filemode='w'
    )


def send_message(bot: Bot, message: str) -> None:
    """Отправляем сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(
            f'Невозможно отправить сообщение. {error}'
        )


def get_api_answer(current_timestamp: int) -> dict:
    """Делаем запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception:
        raise GetAPIAnswerError()
    if homework_statuses.status_code != HTTPStatus.OK:
        logging.error(
            'Ошибка при запросе к эндпоинту API', exc_info=True
        )
        raise GetAPIAnswerError()
    return homework_statuses.json()


def check_response(response: dict) -> dict:
    """Проверка ответа API на корректность."""
    try:
        homeworks = response['homeworks']
        homework = homeworks[0]
        if response != HTTPStatus.OK:
            logging.error('API не отвечает')
        if type(homework) != dict:
            logging.error('Ответ от API имеет некорректный тип')
            raise CheckResponseError
        if homework == '':
            logging.error('В списке нет домашних заданий')
            raise CheckResponseError
    except AttributeError as error:
        logging.error(f'Тип ответа от API: {error}')
    except IndexError as error:
        logging.error(f'Нет работы на проверке: {error}')
    else:
        return homework


def parse_status(homework: dict) -> str:
    """Извлекаем информацию о статусе домашней работы."""
    if 'homework_name' not in homework:
        logging.error('В списке нет домашних заданий')
        raise KeyError()
    homework_name = homework['homework_name']
    if homework['status'] not in HOMEWORK_STATUSES.keys():
        logging.error('Отсутствует статус ревью')
        raise ParseStatusError
    if homework_name not in homework['homework_name']:
        logging.error('Отсутствует название работы')
        raise ParseStatusError
    verdict = HOMEWORK_STATUSES.get(homework['status'])
    if verdict is None:
        logging.error('Пустой verdict')
        raise ParseStatusError
    return f'Изменился статус проверки работы ' \
           f'"{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяем наличие переменных окружения."""
    if not (PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        logging.critical(f'У объекта/-ов нет переменной окружения.')
        return False
    return True


class GetAPIAnswerError(Exception):
    pass


class CacheTokenError(Exception):
    pass


class ParseStatusError(Exception):
    pass


class CheckResponseError(Exception):
    pass


def main() -> None:
    """Запуск бота."""
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    last_message = None
    last_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if homework is not None and message != last_message:
                send_message(bot, message)
                last_message = message
                time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error:
                send_message(bot, message)
                last_error = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
