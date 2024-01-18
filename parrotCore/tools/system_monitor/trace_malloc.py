import time
import tracemalloc
from utils import abspath
from utils.logger_tools import get_general_logger


class TraceMalloc:

    def __init__(self, enable_debug_malloc=False, my_logger=None):
        self.logger = my_logger or get_general_logger('TraceMalloc',
                                                      path=abspath("tools", "system_monitor", "logs"))

        self.time_last_malloc = 0
        self.enable_debug_malloc = enable_debug_malloc
        self.snapshot1 = None

        if self.enable_debug_malloc:
            self.turn_on()

    def trace_memory(self):
        if self.enable_debug_malloc:
            if time.time() - self.time_last_malloc > 60 * 1:
                snapshot2 = tracemalloc.take_snapshot()
                top_stats = snapshot2.compare_to(self.snapshot1, 'lineno')
                self.snapshot1 = snapshot2
                self.logger.info("[ Top 10 differences ]")
                for stat in top_stats[:10]:
                    self.logger.info(stat)
                top_stats = snapshot2.statistics('traceback')
                stat = top_stats[0]
                self.logger.info("%s memory blocks: %.1f KiB" % (
                    stat.count, stat.size / 1024))
                for line in stat.traceback.format():
                    self.logger.info(line)
                stat = top_stats[1]
                self.logger.info("%s memory blocks: %.1f KiB" % (
                    stat.count, stat.size / 1024))
                for line in stat.traceback.format():
                    self.logger.info(line)
                stat = top_stats[2]
                self.logger.info("%s memory blocks: %.1f KiB" % (
                    stat.count, stat.size / 1024))
                for line in stat.traceback.format():
                    self.logger.info(line)
                self.time_last_malloc = time.time()

    def turn_on(self):
        self.enable_debug_malloc = True
        tracemalloc.start(25)
        self.snapshot1 = tracemalloc.take_snapshot()


if __name__ == '__main__':
    trace = TraceMalloc()
    trace.turn_on()

    for i in range(100):
        trace.trace_memory()
        time.sleep(0.01)
