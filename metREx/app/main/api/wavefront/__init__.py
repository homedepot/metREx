from .. import ApiAccessLayer


class Wavefront(ApiAccessLayer):
    client = None

    def init_aa(self, bind):
        super(Wavefront, self).init_aa(bind)

        self.client = self.service.client
