import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot


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
    except telegram.TelegramError as error:
        raise TelegramError(
            f'Невозможно отправить сообщение. {error}'
        )
    else:
        logging.info('Сообщение успешно отправлено.')


def get_api_answer(current_timestamp: int) -> dict:
    """Делаем запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logging.info('Делаем запрос к эндпоинту API-сервиса.')
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        raise GetAPIAnswerError(
            f'Что-то не так с ссылкой {ENDPOINT}. {error} '
            f'где заголовок {HEADERS} '
            f'с следующими параметрами {params}'

        )
    else:
        if homework_statuses.status_code != HTTPStatus.OK:
            raise GetAPIAnswerError(
                f'Ошибка {homework_statuses.status_code} '
                f'по адресу {ENDPOINT}, где заголовок {HEADERS} '
                f'с следующими параметрами {params}'
            )
        return homework_statuses.json()


def check_response(response: dict) -> dict:
    """Проверка ответа API на корректность."""
    logging.info('Проверяем ответ API на корректность.')
    if not isinstance(response, dict):
        raise TypeError(
            'Ответ от API не является словарём'
        )
    if 'homeworks' not in response:
        raise CheckResponseError('В ответе от API нет ключа "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise CheckResponseError(
            'По ключу "homeworks" возвращается не список.'
        )
    if len(response['homeworks']) == 0:
        raise CheckResponseError(
            'В данный момент нет домашних заданий на проверке'
        )
    homeworks = response['homeworks']
    homework = homeworks[0]
    return homework


def parse_status(homework: dict) -> str:
    """Извлекаем информацию о статусе домашней работы."""
    logging.info('Извлекаем информацию о статусе домашней работы.')
    if 'homework_name' not in homework:
        raise KeyError(
            'В полученном домашнем задании нет ключа "homework_name"'
        )
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise ParseStatusError('Отсутствует статус в домашней работе')
    if homework['status'] not in HOMEWORK_STATUSES:
        raise ParseStatusError(
            'Статус не соответствует известным нам статусам'
        )
    if 'homework_name' not in homework:
        raise ParseStatusError('Отсутствует название работы')
    verdict = HOMEWORK_STATUSES.get(homework['status'])
    if verdict is None:
        raise ParseStatusError('Пустой verdict')
    return (
        'Изменился статус проверки работы '
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
    for variable_name, variable_value in values:
        if variable_value is None:
            logging.critical(
                f'У объекта "{variable_name}" нет переменной окружения.'
            )
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))

class GetAPIAnswerError(Exception):
    def __init__(self, error):
        self.message = f'API не отвечает. {error}'

    def __str__(self):
        return self.message


class ParseStatusError(Exception):
    def __init__(self, error):
        self.message = (
            f'Есть проблемы с извлекаемой информацией из статуса работы. {error}'
        )

    def __str__(self):
        return self.message


class CheckResponseError(Exception):
    def __init__(self, error):
        self.message = (
            'При проверке ответа API '
            f'на корректность возникли проблемы. {error}'
        )

    def __str__(self):
        return self.message



def main() -> None:
    """Запуск бота."""
    if check_tokens() is False:
        sys.exit('Потерялись переменные окружения')

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

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.info(message)
            if message != last_error:
                send_message(bot, message)
                last_error = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
