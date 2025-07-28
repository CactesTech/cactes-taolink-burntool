from threading import Thread, Event, RLock

class BurnToolTimer(Thread):
    def __init__(self, function, interval=0.01, args=None, kwargs=None):
        Thread.__init__(self)
        self.interval = interval
        self.startwait_interval = 0.01
        self.function = function
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}
        self.polling = Event()
        self.rlock = RLock()
        self._sta = 0
        self._next_sta = None
        self.destroy_event = Event()
        super().start()

    '''
    sta: 0 stop
    sta: 1 repeated running,
    sta: 2 first running,
    sta: 3 update interval
    '''
    def stop(self):
        self._next_sta = 0
        self.polling.set()

    def start(self, interval=0.01):
        self.rlock.acquire()
        self.startwait_interval = interval
        self._next_sta = 2
        self.polling.set()
        self.rlock.release()

    def set_interval(self, interval):
        self.rlock.acquire()
        self.interval = interval
        self._next_sta = 3
        self.polling.set()
        self.rlock.release()

    def destory(self):
        self.rlock.acquire()
        self.polling.set()
        self.destroy_event.set()
        self.rlock.release()

    def run(self):
        while not self.destroy_event.is_set():
            self.rlock.acquire()
            if self._next_sta != None:
                self._sta = self._next_sta
                self._next_sta = None

            if self._sta == 0:
                interval = None
            elif self._sta == 1:
                self.function(*self.args, **self.kwargs)
                interval = self.interval
            elif self._sta == 2:
                self._sta = 1
                interval = self.startwait_interval
            else:
                self._sta = 1
                interval = self.interval
            self.rlock.release()

            # print(f"timer sta {self._sta}, interval {interval}")

            if not self.destroy_event.is_set():
                self.polling.wait(interval)
                if self.polling.is_set():
                    self.polling.clear()

        self.polling.clear()
        self._sta = 0
        self._next_sta = None
