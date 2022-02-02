from .. import ApiAccessLayer


class NewRelic(ApiAccessLayer):
    account_id = None
    client = None

    def init_aa(self, bind):
        super(NewRelic, self).init_aa(bind)

        self.account_id = self.service.account_id
        self.client = self.service.client
