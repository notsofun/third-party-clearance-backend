from abc import ABC, abstractmethod

class StateHandler(ABC):

    def __init__(self):
        super().__init__()

        self.CONTINUE = 'continue'
        self.NEXT = 'next'

    def check(self, status):
        if status == self.CONTINUE:
            print('ok')
        elif status == self.NEXT:
            print('not ok')

s = StateHandler()

resi = s.check('continue')
print(resi)