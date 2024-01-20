from tools.streaming.revents import Worker
from blueprints.account.controllers import AccountController
from blueprints.account.models import (
    Accounts,
    AccountsVocab,
    AccountsScores,
    Users
)

core_worker = Worker()


@core_worker.on('broker', "account_register")
def account_register(user_id=None):
    if user_id:
        AccountController().register_user(int(user_id), [1])
        print(f"Create account {user_id} processed.")
        return True
    else:
        print(f"Create account {user_id} failed.")

def main():
    print("开始监听....")
    core_worker.listen(listen_name='broker')

