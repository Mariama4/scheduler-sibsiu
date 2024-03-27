from aiogram.utils.markdown import hbold, hlink
from helpers import helper


def get_start_text(user_full_name):
    return f"""Привет! {hbold(user_full_name)}
В этом боте ты можешь получить расписание или подписаться на обновления расписания, чтобы ничего не пропустить!
"""


def get_file_params_text(document):
    return f"""{hbold('Институт')}: {document['institute_local_name']}
{hbold('Имя файла')}: {hlink(document['file_name'], document['file_link'])}
{hbold('Дата обновления на сайте')}: {helper.timestamp_to_local_time(document['file_last_modified'])}
{hbold('Дата обновления в боте')}: {helper.timestamp_to_local_time(document['timestamp'])}"""
