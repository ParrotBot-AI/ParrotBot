from tools.streaming.revents import Worker

admin_worker = Worker()


@admin_worker.on('core_broker', "register_microservices")
def test(foo, test=False):
    if not bool(test):
        print('test')
    else:
        print('tested')


if __name__ == "__main__":
    admin_worker.listen(listen_name='core_broker')