# hashmap.py
from enum import Enum

class Variables(Enum):
    SPEED = 0
    ALTITUDE = 1
    ERROR = 2
    EOR = 3
    ERPOR = 4
    def __str__(self):
        return self.name
