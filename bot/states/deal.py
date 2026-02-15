from aiogram.fsm.state import State, StatesGroup


class DealMessageFSM(StatesGroup):
    waiting_for_text = State()


class CreativeSubmitFSM(StatesGroup):
    waiting_for_post = State()
    confirm_creative = State()


class CreativeReviewFSM(StatesGroup):
    waiting_for_feedback = State()


class SchedulePostFSM(StatesGroup):
    waiting_for_datetime = State()
    confirm_schedule = State()


class DealBriefFSM(StatesGroup):
    waiting_for_brief = State()
    waiting_for_publish_from = State()
    waiting_for_publish_to = State()
    confirm_and_send = State()


class AmendmentProposalFSM(StatesGroup):
    waiting_for_price = State()
    waiting_for_publish_date = State()
    confirm = State()
