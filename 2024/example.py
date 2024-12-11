#!/usr/bin/python
class node():
    def __init__(self, value):
        self.next = None
        self.value = value
    def __iter__(self):
        return self
    def __next__(self):
        if self.next:
            return self.next
        raise StopIteration

head = node(-1)
tail = head
for i in range(10):
    tail.next = node(i)
    tail = tail.next

for n in head:
    print(n.value)
