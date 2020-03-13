from .. import ApiAccessLayer


class GitHub(ApiAccessLayer):
    client = None

    def init_aa(self, bind):
        super(GitHub, self).init_aa(bind)

        self.client = self.service.client
