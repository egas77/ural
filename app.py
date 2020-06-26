from selenium import webdriver
import vk_api
import random
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard
from time import sleep
from threading import Thread
import json
import requests
from flask import Flask
import os

driver_path = 'phantomjs'

REGISTRATION_URL = 'https://checkin.uralairlines.ru/'

TOKEN_VK = 'd5dc5c9bbe04f1b2b9ebdf016571ed31da862128b95e83162581b329d1093582b73c39d026104e7cbe11b'
vk_session = vk_api.VkApi(
    token=TOKEN_VK
)
vk = vk_session.get_api()

longpol = VkBotLongPoll(vk_session, 194080418)
TOKEN = 'd5dc5c9bbe04f1b2b9ebdf016571ed31da862128b95e83162581b329d1093582b73c39d026104e7cbe11b'
vk_session = vk_api.VkApi(
    token=TOKEN
)

keyboard = VkKeyboard(one_time=False)
keyboard.add_button('Пользователи')
keyboard.add_button('Добавить пользователя')
keyboard.add_button('Информация о пользователе')
keyboard.add_line()
keyboard.add_button('Удалить пользователя')
keyboard.add_line()
keyboard.add_button('Восстановить пользователя')
keyboard.add_line()
keyboard.add_button('Включить уведомления')
keyboard.add_line()
keyboard.add_button('ВЫКЛЮЧИТЬ уведомления')

back_keyboard = VkKeyboard(one_time=False)
back_keyboard.add_button('Назад')


def check_user(driver, user):
    driver.get(REGISTRATION_URL)
    lastname = driver.find_element_by_name('lastname')
    lastname.send_keys(user['lastname'])
    ticket = driver.find_element_by_name('ticket')
    ticket.send_keys(user['ticket'])
    ticket.submit()
    if 'passengers' in driver.current_url:
        return True
    return False


def send_user_info(driver, user):
    button = driver.find_element_by_class_name('flight_num')
    button.click()
    name = driver.find_element_by_class_name('psgr-name').text
    msg = '''Регистрация для пассажира {0} открыта!
                Для регитрации перейдите по ссылке {1}
                Фамилия: {2}
                Тикет: {3}'''.format(name, REGISTRATION_URL, user['lastname'], user['ticket'])
    with open('vk_users.json', mode='r', encoding='utf-8') as json_file:
        users = json.load(json_file)['users']
    for user_id in users:
        vk.messages.send(user_id=user_id, message=msg,
                         random_id=random.randint(0, 2 ** 64))


def start_check():
    driver = webdriver.PhantomJS(driver_path)

    while True:
        with open('users.json', mode='r', encoding='utf-8') as json_file:
            try:
                data = json.load(json_file)
                done_users = data['done']
            except json.decoder.JSONDecodeError:
                continue
        for user in data['users']:
            if user in done_users:
                continue
            if check_user(driver, user):
                send_user_info(driver, user)
                data['done'].append(user)
                with open('users.json', mode='w', encoding='utf-8') as json_file:
                    json.dump(data, json_file)
        sleep(60 * 10)


def get_users_msg():
    with open('users.json', mode='r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    users = data['users']
    done_users = data['done']
    strings = list()
    for user in enumerate(users):
        index = user[0]
        current_user = user[1]
        current_string = '{0}. {1}'.format(index, current_user['lastname'])
        if current_user in done_users:
            current_string += ' [ЗАВЕРШЕН]'
        strings.append(current_string)
    msg = '\n'.join(strings)
    return msg


def user_dialog(user_id):
    msg = get_users_msg()
    vk.messages.send(user_id=user_id, message=msg,
                     keyboard=keyboard.get_empty_keyboard(),
                     random_id=random.randint(0, 2 ** 64))
    vk.messages.send(user_id=user_id, message='Введите номер пользователя:',
                     keyboard=back_keyboard.get_keyboard(),
                     random_id=random.randint(0, 2 ** 64))
    for event in longpol.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            message = event.message['text'].lower()
            if message == 'назад':
                return None
            else:
                return message


def start_longpol():
    driver = webdriver.PhantomJS(driver_path)

    for event in longpol.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            user_id = event.message['from_id']
            message = event.message['text'].lower()
            if message == 'пользователи':
                msg = get_users_msg()
                vk.messages.send(user_id=user_id, message=msg, keyboard=keyboard.get_keyboard(),
                                 random_id=random.randint(0, 2 ** 64))

            elif message == 'включить уведомления':
                with open('vk_users.json', mode='r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                if user_id in data['users']:
                    msg = 'У вас уже включены уведомления!'
                else:
                    msg = 'Уведомления успешно включены!'
                    data['users'].append(user_id)
                    with open('vk_users.json', mode='w', encoding='utf-8') as json_file:
                        json.dump(data, json_file)
                vk.messages.send(user_id=user_id, message=msg, keyboard=keyboard.get_keyboard(),
                                 random_id=random.randint(0, 2 ** 64))

            elif message == 'выключить уведомления':
                with open('vk_users.json', mode='r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
                if user_id in data['users']:
                    msg = 'Уведомления успешно выключены!'
                    data['users'].pop(data['users'].index(user_id))
                    with open('vk_users.json', mode='w', encoding='utf-8') as json_file:
                        json.dump(data, json_file)
                else:
                    msg = 'У вас не включены уведомления!'
                vk.messages.send(user_id=user_id, message=msg, keyboard=keyboard.get_keyboard(),
                                 random_id=random.randint(0, 2 ** 64))

            elif message == 'удалить пользователя':
                message = user_dialog(user_id)
                if not message:
                    msg = 'Главное меню'
                else:
                    try:
                        if not message.isdigit():
                            raise ValueError
                        user_index = int(message)
                        with open('users.json', mode='r', encoding='utf-8') as json_file:
                            data = json.load(json_file)
                        user = data['users'][user_index]
                        data['users'].remove(user)
                        msg = 'Пользователь успешно удален'
                        if user in data['done']:
                            data['done'].remove(user)
                        with open('users.json', mode='w', encoding='utf-8') as json_file:
                            json.dump(data, json_file)
                    except (IndexError, ValueError):
                        msg = 'Пользователь не найден'
                vk.messages.send(user_id=user_id, message=msg,
                                 keyboard=keyboard.get_keyboard(),
                                 random_id=random.randint(0, 2 ** 64))

            elif message == 'восстановить пользователя':
                message = user_dialog(user_id)
                if not message:
                    msg = 'Главное меню'
                else:
                    try:
                        if not message.isdigit():
                            raise ValueError
                        user_index = int(message)
                        with open('users.json', mode='r', encoding='utf-8') as json_file:
                            data = json.load(json_file)
                        user = data['users'][user_index]
                        if user in data['done']:
                            data['done'].remove(user)
                        else:
                            raise ValueError
                        with open('users.json', mode='w', encoding='utf-8') as json_file:
                            json.dump(data, json_file)
                        msg = 'Пользователь успешно восстановлен'
                    except (IndexError, ValueError):
                        msg = 'Пользователь не найден'
                vk.messages.send(user_id=user_id, message=msg,
                                 keyboard=keyboard.get_keyboard(),
                                 random_id=random.randint(0, 2 ** 64))
            elif message == 'информация о пользователе':
                message = user_dialog(user_id)
                if not message:
                    msg = 'Главное меню'
                else:
                    try:
                        if not message.isdigit():
                            raise ValueError
                        user_index = int(message)
                        with open('users.json', mode='r', encoding='utf-8') as json_file:
                            data = json.load(json_file)
                        user = data['users'][user_index]
                        vk.messages.send(user_id=user_id, message='Запрос выполняется...',
                                         keyboard=keyboard.get_empty_keyboard(),
                                         random_id=random.randint(0, 2 ** 64))

                        if check_user(driver, user):
                            send_user_info(driver, user)
                            msg = 'Главное меню'
                        else:
                            msg = 'Информация недоступна'
                    except (IndexError, ValueError):
                        msg = 'Пользователь не найден'
                vk.messages.send(user_id=user_id, message=msg,
                                 keyboard=keyboard.get_keyboard(),
                                 random_id=random.randint(0, 2 ** 64))

            elif message == 'добавить пользователя':
                try:
                    vk.messages.send(user_id=user_id, message='Введите фамилию',
                                     keyboard=back_keyboard.get_keyboard(),
                                     random_id=random.randint(0, 2 ** 64))
                    for event in longpol.listen():
                        if event.type == VkBotEventType.MESSAGE_NEW:
                            lastname = event.message['text'].upper()
                            if lastname == 'назад':
                                raise ValueError
                            break

                    vk.messages.send(user_id=user_id, message='Введите номер брони/билета',
                                     keyboard=back_keyboard.get_keyboard(),
                                     random_id=random.randint(0, 2 ** 64))
                    for event in longpol.listen():
                        if event.type == VkBotEventType.MESSAGE_NEW:
                            ticket = event.message['text']
                            if ticket == 'назад':
                                raise ValueError
                            break

                    with open('users.json', mode='r', encoding='utf-8') as json_file:
                        data = json.load(json_file)

                    user = {
                        'lastname': lastname,
                        'ticket': ticket
                    }

                    if user not in data['users']:
                        data['users'].append(user)
                        with open('users.json', mode='w', encoding='utf-8') as json_file:
                            json.dump(data, json_file)
                    vk.messages.send(user_id=user_id, message='Пользователь успешно добавлен',
                                     keyboard=keyboard.get_keyboard(),
                                     random_id=random.randint(0, 2 ** 64))
                except ValueError:
                    vk.messages.send(user_id=user_id, message='Главное меню',
                                     keyboard=keyboard.get_keyboard(),
                                     random_id=random.randint(0, 2 ** 64))

            else:
                msg = 'Команда не найдена'
                vk.messages.send(user_id=user_id, message=msg, keyboard=keyboard.get_keyboard(),
                                 random_id=random.randint(0, 2 ** 64))


def not_sine():
    requests.get('https://yandex.ru/')
    sleep(60 * 5)


if __name__ == '__main__':
    thr_check = Thread(target=start_check)
    thr_check.start()
    thr_long_poll = Thread(target=start_longpol)
    thr_long_poll.start()
    thr_sine = Thread(target=not_sine)
    thr_sine.start()
    port = os.environ.get('PORT', 5000)
    app = Flask(__name__)
    app.run(host='0.0.0.0', port=port)
