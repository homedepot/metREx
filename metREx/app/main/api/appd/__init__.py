from .. import ApiAccessLayer


class AppD(ApiAccessLayer):
    client = None

    application_id = None

    def init_aa(self, bind):
        super(AppD, self).init_aa(bind)

        self.client = self.service.client
