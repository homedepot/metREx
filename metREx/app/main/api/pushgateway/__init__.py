from .. import ApiAccessLayer


class Pushgateway(ApiAccessLayer):
    client = None

    def init_aa(self, bind):
        super(Pushgateway, self).init_aa(bind)

        self.client = self.service.client
