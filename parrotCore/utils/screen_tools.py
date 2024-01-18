import os
from utils import abspath, pprint
import time


# set up the screen tools

def ls_screen(screen_name):
    screen_info = os.popen(f'screen -ls').read()
    screen_list = screen_info.split('\n')

    if len(screen_list) == 2:
        return []

    screen_infos = []
    for row in screen_list[1:-1]:
        if screen_name in row:
            _, raw_screen_pid, raw_time, raw_status = row.split('\t')
            screen_infos.append({
                'pid': raw_screen_pid.split('.')[0],
                'name': raw_screen_pid[raw_screen_pid.find('.'):][1:],
                'startTime': raw_time[1:-1],
                'status': raw_status[1:-1]
            })

    return screen_infos


def stop_screen(uid, force=False):
    screen_info = os.popen(f'screen -ls').read()
    screen_list = screen_info.split('\n')
    pids = []
    for row in screen_list:
        if uid in row:
            screen_pid = row.split('.')[0].strip()
            if force:
                command = f'screen -XS {screen_pid} quit'
            else:
                command = f'screen -S {screen_pid} -X stuff "^C"'
            resp = os.system(command)
            pids.append(screen_pid)
    return pids


if __name__ == '__main__':
    pprint(ls_screen('frontend'))
