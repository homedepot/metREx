from multiprocessing import get_context

ctx = get_context('fork')


class Process(ctx.Process):
    def __init__(self, *args, **kwargs):
        super(Process, self).__init__(*args, **kwargs)

        self._pconn, self._cconn = ctx.Pipe(duplex=False)
        self._exception = None

    def run(self):
        try:
            super(Process, self).run()

            self._cconn.send(None)
        except Exception as e:
            self._cconn.send(e)
        finally:
            self._cconn.close()
            self._pconn.close()

    @property
    def exception(self):
        if self._pconn.poll():
            self._exception = self._pconn.recv()

        return self._exception


__all__ = [
    'Process',
    'ctx'
]
