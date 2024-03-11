import asyncio
import os
import time
from io import BytesIO
import pdf2image
import requests
import aiohttp
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.utils.media_group import MediaGroupBuilder
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
import pytz
from config import EXPIRATION_TIME_LIMIT_SECONDS
from helpers import stored_text
from loader import mongodb


def get_schedule_data():
    def normalize_url(url, schema='https'):
        url = f'{schema}://{url}'
        url = url.replace('\\', '/')
        url = url.replace(' ', '%20')
        return url

    base_url = 'https://www.sibsiu.ru/raspisanie/'
    parsed_url = urlparse(base_url)
    response = requests.get(base_url)

    soup = BeautifulSoup(response.text, 'lxml')

    file_links = soup.find_all('li', class_='ul_file')
    result = []

    for link in file_links:
        parent = link.parent
        while True:
            if parent.has_attr('class'):
                if 'institut_div' in parent.attrs['class']:
                    break
            parent = parent.parent

        institute_local_name = parent.p.text
        file_link = normalize_url(
            url=(parsed_url.hostname + link.a['href']),
            schema=parsed_url.scheme
        )
        parsed_url = urlparse(file_link)
        file_name = link.string

        institute_name = parsed_url.path.split('/')[3]

        institute_name = institute_name.lstrip().rstrip()
        institute_local_name = institute_local_name.lstrip().rstrip()
        file_name = file_name.lstrip().rstrip()
        file_link = file_link.lstrip().rstrip()

        result.append({
            'institute_name': institute_name,
            'institute_local_name': institute_local_name,
            'file_name': file_name,
            'file_link': file_link,
        })

    return result


def get_last_file_update(response, datetime_format='%a, %d %b %Y %H:%M:%S %Z'):
    if 'Last-Modified' not in response.headers:
        raise ValueError("Last-Modified header не найден")

    last_modified = response.headers['Last-Modified']
    timestamp = datetime.strptime(last_modified, datetime_format).timestamp()
    return timestamp


def get_images_from_url_pdf(url, max_retries=10, wait_time=1, backoff_factor=2):
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url)
            response.raise_for_status()
            images = pdf2image.convert_from_bytes(response.content, dpi=300)
            result = []

            for i, v in enumerate(images):
                buf = BytesIO()
                v.save(buf, format('PNG'))
                buf.seek(0)
                result.append(buf)

            return result
        except Exception as e:
            retries += 1
            wait_time *= backoff_factor
            print(
                f"Error fetching images from {url}. Retrying in {wait_time:.2f} seconds (attempt {retries + 1} of {max_retries})...")
            time.sleep(wait_time)
    print(f"Failed to fetch images from {url} after {max_retries} retries.")
    return []


async def get_filepath_images_from_pdf(response):
    data = await response.content.read()
    images = pdf2image.convert_from_bytes(data, dpi=300)
    result = []

    for i, v in enumerate(images):
        abs_filepath = os.path.abspath(f'temp/{response.url_obj.parts[3]}-{response.url_obj.name}-{i}.png')
        v.save(abs_filepath, 'PNG')
        result.append(abs_filepath)

    return result


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def get_media_groups_from_filepaths(images):
    result = []
    for images_chunk in chunks(images, 10):
        album_builder = MediaGroupBuilder()
        for image in images_chunk:
            album_builder.add_photo(
                media=FSInputFile(
                    image
                )
            )
        result.append(album_builder)
    return result


def timestamp_to_local_time(timestamp, timezone_name="Asia/Novokuznetsk"):
    dt = datetime.fromtimestamp(timestamp, pytz.utc)
    tz = pytz.timezone(timezone_name)
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


async def update_schedule_and_notify_users(bot):
    documents = await collect_data()
    updated_documents = await mongodb.upsert_schedule(documents, time_limit=EXPIRATION_TIME_LIMIT_SECONDS)
    deleted_documents = await mongodb.delete_old_documents(time_limit=EXPIRATION_TIME_LIMIT_SECONDS)
    await notify_users_about_update(bot, updated_documents)
    await delete_old_schedule_notify_users(bot, deleted_documents)


async def notify_users_about_update(bot, updated_documents):
    for document in updated_documents:
        if 'subscribers' in document:
            media_groups = get_media_groups_from_filepaths(document['images_filepath'])
            text = f'Расписание обновилось!\n{stored_text.get_file_params_text(document)}'
            builder = InlineKeyboardBuilder()
            kb = builder.add(InlineKeyboardButton(
                text="Отписаться",
                callback_data=f"unsubscribe_{document['_id']}"),
            ).as_markup()

            for subscriber in document['subscribers']:
                for mg in media_groups:
                    await bot.send_media_group(
                        media=mg.build(),
                        chat_id=subscriber
                    )
                await bot.send_message(text=text,
                                       reply_markup=kb,
                                       chat_id=subscriber)


async def delete_old_schedule_notify_users(bot, deleted_documents):
    for document in deleted_documents:
        if 'subscribers' in document:
            text = f'Документ не обнаружен на сайте! Подписка отменена!\n{stored_text.get_file_params_text(document)}'
            for subscriber in document['subscribers']:
                await bot.send_message(
                    text=text,
                    chat_id=subscriber
                )


async def worker(session, link_object, max_retries=10):
    retries = 0
    while retries < max_retries:
        try:
            async with session.get(link_object['file_link']) as response:
                last_modified = get_last_file_update(response)
                link_object['file_last_modified'] = last_modified
                link_object['images_filepath'] = await get_filepath_images_from_pdf(response)
                link_object['timestamp'] = datetime.now().timestamp()
                return link_object
        except Exception as e:
            retries += 1
            print(f"Error processing {link_object['file_link']}: {e}. Retrying (attempt {retries+1} of {max_retries})")
            await asyncio.sleep(1 + retries)
    print(f"Failed to process {link_object['file_link']} after {max_retries} retries.")
    return None


async def collect_data_in_chunks(link_objects, chunk_size=10):
    async with aiohttp.ClientSession() as session:
        all_results = []
        for i in range(0, len(link_objects), chunk_size):
            chunk = link_objects[i:i + chunk_size]

            tasks = [worker(session, link_object) for link_object in chunk]
            results = await asyncio.gather(*tasks)

            all_results.extend(results)

        return all_results


async def collect_data():
    PATH = os.path.abspath(f'temp')
    if not os.path.exists(PATH):
        os.makedirs(PATH)

    link_objects = get_schedule_data()
    results = await collect_data_in_chunks(link_objects)
    return results


def make_row_keyboard(items: list[str], placeholder: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for item in items:
        builder.add(
            KeyboardButton(text=item)
        )
    builder.adjust(1)
    kb = builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=placeholder
    )
    return kb
