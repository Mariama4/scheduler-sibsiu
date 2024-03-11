import asyncio
import logging
import sys

from aiogram.utils.keyboard import InlineKeyboardBuilder
from bson import ObjectId

from FSMStates.schedule import SelectSchedule
from middlewares.throttling import ThrottlingMiddleware
from loader import dp, mongodb, configuration
from helpers import helper, stored_text
import jobs

from aiogram import Bot, flags, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, BotCommand, CallbackQuery, InlineKeyboardButton

from aiogram.utils.chat_action import ChatActionMiddleware
from aiogram.fsm.context import FSMContext


@dp.message(CommandStart())
@flags.chat_action(action="typing")
async def command_start_handler(message: Message) -> None:
    text = stored_text.get_start_text(message.from_user.full_name)
    await message.answer(text)


@dp.message(StateFilter(None), Command('schedule'))
@flags.chat_action(action="typing")
async def text_schedule_handler(message: Message, state: FSMContext):
    institutes = await mongodb.get_all_institutes()
    if len(institutes) == 0:
        await message.answer(text='В базе нет институтов')
        return
    kb = helper.make_row_keyboard(institutes, 'Выберите институт:')
    await message.answer(text='Выберите институт', reply_markup=kb)
    await state.set_state(SelectSchedule.choosing_institute_name)


@dp.message(SelectSchedule.choosing_institute_name)
@flags.chat_action(action="typing")
async def institute_chosen(message: Message, state: FSMContext):
    institutes = await mongodb.get_all_institutes()
    if message.text not in institutes:
        return await text_schedule_handler(message, state)

    await state.update_data(chosen_institute=message.text)

    result = await mongodb.get_file_names(message.text)

    if len(result) == 0:
        await message.answer(text='В базе нет файлов')
        await state.clear()
        return

    kb = helper.make_row_keyboard(result, 'Выберите файл:')

    await message.answer(text='Выберите файл', reply_markup=kb)
    await state.set_state(SelectSchedule.choosing_file_name)


@dp.message(SelectSchedule.choosing_file_name)
@flags.chat_action(action="upload_photo")
async def file_name_chosen(message: Message, state: FSMContext):
    user_data = await state.get_data()
    await state.clear()
    file_names = await mongodb.get_file_names(institute_local_name=user_data['chosen_institute'])
    if message.text not in file_names:
        return await institute_chosen(message, state)

    document = await mongodb.get_document_by_institute_local_name_and_file_name(
        institute_local_name=user_data['chosen_institute'],
        file_name=message.text)

    await message.answer(text='Пожалуйста, подождите, файлы отправляются...')

    media_groups = helper.get_media_groups_from_filepaths(document['images_filepath'])

    for mg in media_groups:
        await message.answer_media_group(
            media=mg.build()
        )
    text = stored_text.get_file_params_text(document)

    is_user_subscribed = await mongodb.check_is_user_subscribed(message.from_user.id,
                                                                document['_id'])
    builder = InlineKeyboardBuilder()

    if is_user_subscribed:
        builder.add(InlineKeyboardButton(
            text="Отписаться",
            callback_data=f"unsubscribe_{document['_id']}"),
        )
    else:
        builder.add(InlineKeyboardButton(
            text="Подписаться",
            callback_data=f"subscribe_{document['_id']}"),
        )
    kb = builder.as_markup()
    await message.answer(text=text, reply_markup=kb)


@dp.message(StateFilter(None), Command('subscriptions'))
@flags.chat_action(action="typing")
async def user_subscriptions(message: Message):
    documents = await mongodb.get_documents_by_user_id(user_id=message.from_user.id)

    if len(documents) == 0:
        await message.answer(
            text='Вы не подписаны на обновления'
        )
        return

    for document in documents:
        builder = InlineKeyboardBuilder()
        kb = builder.add(InlineKeyboardButton(
            text="Отписаться",
            callback_data=f"unsubscribe_{document['_id']}"),
        ).as_markup()
        text = stored_text.get_file_params_text(document)
        await message.answer(text=text,
                             disable_web_page_preview=True,
                             reply_markup=kb)


@dp.callback_query(F.data.startswith("subscribe_"))
async def subscribe_user(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    document_id = ObjectId(callback.data.split('_')[1])
    document = await mongodb.get_document_by_id(document_id)
    result = await mongodb.subscribe_user(callback.from_user.id, document['_id'])
    if result:
        await callback.answer(
            text=f"Вы подписались на получение обновлений файла: {document['institute_local_name']} " +
                 f"{document['file_name']}",
            show_alert=True
        )
    else:
        await callback.answer(
            text="Вы не смогли подписаться на получение обновлений",
            show_alert=True
        )


@dp.callback_query(F.data.startswith("unsubscribe_"))
async def unsubscribe_user(callback: CallbackQuery):
    await callback.message.edit_reply_markup()
    document_id = ObjectId(callback.data.split('_')[1])
    document = await mongodb.get_document_by_id(document_id)
    result = await mongodb.unsubscribe_user(callback.from_user.id, document_id)
    if result:
        await callback.message.answer(
            text=f"Вы отписались от получения обновлений файла: {document['institute_local_name']} " +
                 f"{document['file_name']}"
        )
    else:
        await callback.answer(
            text="Вы не смогли отписаться от получения обновлений",
            show_alert=True
        )


async def setup_bot_commands(bot):
    bot_commands = [
        BotCommand(command="schedule", description="Получить расписание"),
        BotCommand(command="subscriptions", description="Твои подписки на обновления файлов"),
    ]
    await bot.set_my_commands(bot_commands)


async def main() -> None:
    bot = Bot(token=configuration['BOT_TOKEN'],
              parse_mode=ParseMode.HTML)
    await setup_bot_commands(bot)
    try:
        jobs.init_jobs(bot)
        dp.message.middleware(ChatActionMiddleware())
        dp.message.middleware(ThrottlingMiddleware(throttle_time=5))
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        mongodb.close_connection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
