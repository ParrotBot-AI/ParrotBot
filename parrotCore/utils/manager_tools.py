import fire
import time
import os
from utils import USERNAME, abspath
from configs.environment import ENV_PATH
from utils.screen_tools import stop_screen, ls_screen
from crontab import CronTab


class ServiceManager:
    name = None
    file = None
    dir_path = None
    schedule = None

    def __init__(self, action):
        if action == 'restart':
            self.restart()

        elif action == 'start':
            self.start()

        elif action == 'stop':
            self.stop()

        elif action == 'run':
            self.run()

        elif action == 'enable':
            self.enable()

        elif action == 'disable':
            self.disable()

        elif action == 'status':
            self.status()

        else:
            print(f'Action "{action}" not valid.')

    def restart(self):
        self.stop()
        time.sleep(3)
        self.start()

    def start(self):
        self._screen_start()
        print(f'{self.name} started.')

    def stop(self):
        self._screen_stop()
        print(f'{self.name} stoped.')

    def run(self):
        print(f'Run script {self.file} at {self.dir_path}/{self.file}')
        command = f"cd {self.dir_path};\
                    {ENV_PATH}/python {self.file}"
        os.system(command)

    def enable(self):
        if not self.schedule:
            raise AttributeError("should provide self.schedule to run enable action")
        cron = CronTab(user=USERNAME)

        # Remove existing job first
        for job in cron.find_comment(self.name):
            print(f'remove old job: {job}')
            job.delete()

        for job in cron.find_command(f'manager {self.name} run'):
            print(f'remove old job: {job}')
            job.delete()

        job = cron.new(command=f'{ENV_PATH}/python {os.path.join(self.dir_path, self.file)}', comment=self.name)
        job.setall(self.schedule)
        if not job.is_valid():
            raise Exception("Job not valid, please check")

        job.enable()
        print(f'create new job: {job}')
        cron.write()

    def disable(self):
        if not self.schedule:
            raise AttributeError("should provide self.schedule to run enable action")
        cron = CronTab(user=USERNAME)

        # Remove existing job first
        for job in cron.find_comment(self.name):
            print(f'remove old job: {job}')
            job.delete()

        for job in cron.find_command(f'manager {self.name} run'):
            print(f'remove old job: {job}')
            job.delete()

        cron.write()

    def status(self):
        # if schedule is provided, means this a background cron mission
        if self.schedule:
            cron = CronTab(user=USERNAME)

            print('Current job:')
            for job in cron.find_comment(self.name):
                print(job)
            cron.write()
        # otherwise it's a screen
        else:
            for screen in ls_screen(self.name):
                print(screen)

    def _screen_start(self):
        command = f"cd {self.dir_path};\
                    screen -dmS {self.name} {ENV_PATH}/python {self.file}"
        os.system(command)

    def _screen_stop(self):
        pids = stop_screen(self.name, force=True)
        for pid in pids:
            print(f'{self.name} screen stopped, pid: {pid}')


SERVICES_MAP = {
}


def run_service(service_name, action):
    """
    action: start | enable | disable | status
    """
    if service_name not in SERVICES_MAP:
        print(f'No such service: {service_name}')
        return

    service = SERVICES_MAP[service_name]
    service(action=action)


def main():
    fire.Fire(run_service)


if __name__ == '__main__':
    main()