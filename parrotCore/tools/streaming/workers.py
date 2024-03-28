from tools.streaming.revents import Worker
from blueprints.account.controllers import AccountController
from blueprints.education.controllers import AnsweringScoringController

import asyncio
core_worker = Worker()


@core_worker.on('broker', "account_register")
def account_register(user_id=None):
    if user_id:
        res, data = AccountController().register_user(int(user_id), [1])
        if res:
            print(f"Create account {user_id} processed.")
        else:
            print(f"Create account {user_id} Failed: {str(data)}.")
    else:
        print(f"Create account {user_id} failed.")


@core_worker.on('broker', "pause_sheet")
def pause_sheet(sheet_id=None):
    if sheet_id:
        res, data = AnsweringScoringController().pause_sheet(sheet_id=sheet_id)
        if res:
            print(f"Pause sheet for user {sheet_id}.")
            return True
        else:
            print(f"Pause sheet for user {sheet_id} failed: {str(data)}")
            return False
    else:
        print(f"Pause sheet {sheet_id} failed.")


@core_worker.on('broker', "save_study_time")
def save_study_time(account_id=None, study_time=None, **kwargs):
    from blueprints.learning.controllers import StudyPulseController
    if account_id and study_time:
        res, data = StudyPulseController().add_pulse_time(account_id=account_id, time_length=study_time)
        if res:
            print(f"Study time record for Account {account_id}.")
            return True
        else:
            print(f"Study time record for Account {account_id} failed: {str(data)}")
            return False
    else:
        print(f"Study time record for Account {account_id} failed.")


@core_worker.on('broker', "grade_single_prob")
def grade_single_prob(sheet_id=None, question_id=None):
    if sheet_id and question_id:
        asyncio.run(AnsweringScoringController().model_scoring(sheet_id=sheet_id, question_id=question_id))
        print(f"Grade for {sheet_id} question {question_id}.")
        return True
    else:
        print(f"Grade for {sheet_id} question {question_id}. failed.")


def main():
    print("开始监听....")
    core_worker.listen(listen_name='broker')
