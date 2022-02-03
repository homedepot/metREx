from .. import ApiAccessLayer


class GraphiteBridge(ApiAccessLayer):
    client = None

    def init_aa(self, bind):
        super(GraphiteBridge, self).init_aa(bind)

        self.client = self.service.client
