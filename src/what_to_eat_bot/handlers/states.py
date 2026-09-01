from aiogram.fsm.state import State, StatesGroup


class AddDish(StatesGroup):
    name = State()
    meal_type = State()
    ingredients = State()
    confirm = State()


class EditDish(StatesGroup):
    menu = State()
    name = State()
    meal_type = State()
    ingredients = State()


class Recommend(StatesGroup):
    extras = State()


class SearchDish(StatesGroup):
    query = State()


class SettingsInput(StatesGroup):
    basic = State()
    favorite = State()


class FamilyFlow(StatesGroup):
    name = State()
    confirm_join = State()
