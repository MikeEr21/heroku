import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

from exceptions import CheckResponseError, GetAPIAnswerError, ParseStatusError

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

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.addHandler(logging.StreamHandler(sys.stdout))


def send_message(bot: Bot, message: str) -> None:
    """Отправляем сообщение в Telegram чат."""
    try:
        logging.info(f'Сообщение "{message}" готовится к отправке.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError:
        logging.error(
            f'Невозможно отправить сообщение.'
        )
    else:
        logging.info(f'Сообщение успешно отправлено.')


def get_api_answer(current_timestamp: int) -> dict:
    """Делаем запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    logging.info('Делаем запрос к эндпоинту API-сервиса.')
    homework_statuses = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params
    )
    if homework_statuses.status_code != HTTPStatus.OK:
        raise GetAPIAnswerError()
    return homework_statuses.json()


def check_response(response: dict) -> dict:
    """Проверка ответа API на корректность."""
    logging.info('Проверяем ответ API на корректность.')
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
    return homework


def parse_status(homework: dict) -> str:
    """Извлекаем информацию о статусе домашней работы."""
    logging.info('Извлекаем информацию о статусе домашней работы.')
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
    return (
        f'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def check_tokens() -> bool:
    """Проверяем наличие переменных окружения."""
    logging.info('Проверяем наличие переменных окружения.')
    values = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    )
    empty_variables = []
    for variable_name, variable_value in values:
        if variable_value is None:
            empty_variables.append(variable_name)
            logging.critical(f'У объекта/-ов "{empty_variables[0]}" нет переменной окружения.')
            return False
    return True


class GetAPIAnswerError(Exception):
    def __init__(self):
        self.message = 'API не отвечает.'

    def __str__(self):
        return self.message


class ParseStatusError(Exception):
    def __init__(self):
        self.message = (
            'Есть проблемы с извлекаемой информацией из статуса работы.'
        )

    def __str__(self):
        return self.message


class CheckResponseError(Exception):
    def __init__(self):
        self.message = (
            """При проверке ответа API
            на корректность возникли проблемы."""
        )

    def __str__(self):
        return self.message


def main() -> None:
    """Запуск бота."""
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = None
    last_error = None

    while check_tokens():
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if homework is not None and message != last_message:
                send_message(bot, message)
                last_message = message

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error:
                send_message(bot, message)
                last_error = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()