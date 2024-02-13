from aiogram.fsm.state import StatesGroup, State


class SelectSchedule(StatesGroup):
    choosing_institute_name = State()
    choosing_file_name = State()
