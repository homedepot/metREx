from .. import ApiAccessLayer


class AppD(ApiAccessLayer):
    application = None
    client = None

    def init_aa(self, bind):
        super(AppD, self).init_aa(bind)

        self.application = self.service.application
        self.client = self.service.client
