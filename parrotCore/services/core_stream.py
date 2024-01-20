from tools.streaming.workers import core_worker
if __name__ == "__main__":
    core_worker.listen(listen_name='broker')
