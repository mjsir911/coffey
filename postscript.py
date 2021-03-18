#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

# postscript parser

from typing import *

from functools import lru_cache

from sys import argv



class PostscriptFunction:
    pass


class Name(str):
    def __repr__(self):
        return f'{type(self).__name__}({super().__repr__()})'


class Block(list):
    def __repr__(self):
        return f'{type(self).__name__}({super().__repr__()})'


class PostscriptOtherFunction(PostscriptFunction):
    def __init__(self, block: Block):
        self.block = block

    def __call__(self, stack):
        stack(self.block)


markStart = object()


def noop(n):
    def wrapper(stack):
        for _ in range(n):
            stack.pop()
    return wrapper


class QuitException(Exception):
    pass


class Runner(list):
    """
    > globaldict /def { globaldict 3 1 roll put } put
    > /cleartomark { unmark pop } def
    """
    globaldict: Dict[str, callable]
    systemdict: Dict[str, Block]

    def __init__(self, *args):
        super().__init__(*args)
        self.globaldict = {}

        from inspect import getmembers

        def fixname(name):
            if name.startswith('func_hex_'):
                return bytes.fromhex(name[9:]).decode()
            return name[5:]
        self.systemdict = {
            fixname(name): meth for name, meth in getmembers(self, callable)
            if name.startswith('func_')
        }

        self.tokenizer = self.tokenize()
        next(self.tokenizer)
        for line in self.prelude():
            for word in self.lex(line):
                self.tokenizer.send(word)

    def stackify(unbound_func):
        from functools import wraps
        from inspect import signature

        @wraps(unbound_func)
        def wrapper(self):
            func = unbound_func.__get__(self)
            numargs = len(signature(func).parameters)
            args = [self.pop() for _ in range(numargs)]
            args.reverse()
            return func(*args)
        return wrapper

    @stackify
    @staticmethod
    def func_add(a, b):
        return a + b

    @stackify
    @staticmethod
    def func_sub(a, b):
        return a - b

    @stackify
    @staticmethod
    def func_bitshift(a, b):
        return a << b

    @stackify
    def func_roll(self, n: int, j: int):
        """roll
        > /exch { 2 1 roll } def
        """
        buf = self[-n:]
        self[-n:] = []

        self.extend(buf[-j:] + buf[:-j])

    @stackify
    @staticmethod
    def func_put(d: dict, key, val):
        d[key] = val

    @stackify
    @staticmethod
    def func_hex_3D(a):
        print(a)

    def func_counttomark(self):
        return self[::-1].index(markStart)

    def func_globaldict(self):
        return self.globaldict

    def func_systemdict(self):
        return self.systemdict

    func_pop = noop(1)

    def func_stack(self):
        print(self)

    @staticmethod
    def func_mark():
        """ [
        > /[ { mark } def
        > /<< { mark } def
        """
        return markStart

    def func_unmark(self):
        """ ]
        > /] { unmark } def
        """
        count = self.func_counttomark()
        ret = self[-count:]
        self[-count - 1:] = []
        return ret

    def func_hex_3E3E(self):
        " >> "
        l = iter(self.func_unmark())
        return dict(zip(l, l))

    def func_quit(self):
        raise QuitException()

    func_run = noop(1)
    func_showpage = noop(0)

    def dispatch_func(self, funcname):
        if funcname not in self.systemdict:
            return self.run(self.globaldict[funcname])
        func = self.systemdict[funcname]
        ret = func()
        if ret is None:
            return
        if not isinstance(ret, tuple):
            ret = (ret,)
        self.extend(ret)
        return ret

    def tokenize(self):
        while True:
            token = yield
            if token.isdigit():
                self.append(int(token))
            elif token.startswith('/'):
                self.append(Name(token[1:]))
            elif token.startswith('('):
                acc = token
                if not token.endswith(')'):
                    while True:
                        token = yield
                        acc += ' ' + token
                        if token.endswith(')'):
                            break
                self.append(acc[1:-1])
            elif token == '{':
                acc = Block()
                while True:
                    token = yield
                    if token == '}':
                        break
                    acc.append(token)
                self.append(acc)
            else:
                self.dispatch_func(token)

    @staticmethod
    def lex(line: str):
        return line.split()

    def prelude(self):
        from inspect import getdoc, getmembers
        for line in (getdoc(self) or '').splitlines():
            if line.startswith('> '):
                yield line[1:].lstrip()
        for name, meth in getmembers(self, callable):
            for line in (getdoc(meth) or '').splitlines():
                if line.startswith('> '):
                    yield line[1:].lstrip()

    def run(self, code):
        stream = iter(code)
        tokenizer = self.tokenize()
        next(tokenizer)
        for word in stream:
            tokenizer.send(word)

    def __call__(self, code: str):
        code = [word for line in code.split('\n')
                if not line.strip().startswith('%')
                for word in self.lex(line)]
        for word in code:
            try:
                self.tokenizer.send(word)
            except QuitException:
                break

        return self


if __name__ == '__main__':
    r = Runner()
    if len(argv) > 1:
        print(r(open(argv[1]).read()))
    else:
        while True:
            r(input('> '))
        # import rlcompleter
        # import readline
        # readline.set_completer(print)
        # readline.parse_and_bind("tab: complete")
        # input('$')
