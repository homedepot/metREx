from .. import ApiAccessLayer


class ExtraHop(ApiAccessLayer):
    client = None

    def init_aa(self, bind):
        super(ExtraHop, self).init_aa(bind)

        self.client = self.service.client
