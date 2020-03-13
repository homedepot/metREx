from abc import ABCMeta, abstractmethod


class ApiAccessLayer:
    __metaclass__ = ABCMeta

    service = None

    def __init__(self, aa):
        self._aa = aa

    @abstractmethod
    def init_aa(self, bind):
        self.service = self._aa.get_service(bind=bind)
