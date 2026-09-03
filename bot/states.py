from aiogram.fsm.state import State, StatesGroup


class DonorAddDonation(StatesGroup):
    choosing_category = State()
    uploading_photo = State()
    entering_description = State()


class DonorShipment(StatesGroup):
    uploading_receipt = State()


class NeedyReservation(StatesGroup):
    entering_name = State()
    entering_address = State()
    entering_phone = State()


class NeedyConfirmation(StatesGroup):
    entering_dua = State()
