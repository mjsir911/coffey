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
        return '/' + super().__str__()


class Block(tuple):
    def __repr__(self):
        return f'{{{" ".join(str(item) for item in self)}}}'


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

    #
    # Arithmetic

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

    #
    # Constants
    @staticmethod
    def func_true():
        return True

    @staticmethod
    def func_false():
        return False

    #
    # Stack helpers

    @stackify
    def func_roll(self, n: int, j: int):
        """roll
        > /exch { 2 1 roll } def
        """
        buf = self[-n:]
        self[-n:] = []

        self.extend(buf[-j:] + buf[:-j])

    func_pop = noop(1)

    @stackify
    @staticmethod
    def func_dup(a):
        return a, a

    #
    # debugging

    @stackify
    @staticmethod
    def func_hex_3D(a):
        " = "
        print(a)

    @stackify
    @staticmethod
    def func_hex_3D3D(a):
        " == "
        print(a)

    def func_stack(self):
        print(self)

    def func_pstack(self):
        print(self)

    #
    # IO

    @stackify
    @staticmethod
    def func_file(fname, mode):
        return open(fname.decode(), mode.decode())

    #
    # Mark functions

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
        if count == 0:
            self.pop()
            return []
        ret = self[-count:]
        self[-count - 1:] = []
        return ret

    def func_counttomark(self):
        return self[::-1].index(markStart)

    def func_hex_3E3E(self):
        " >> "
        l = iter(self.func_unmark())
        return dict(zip(l, l))

    #
    # Dictionary functions

    def func_globaldict(self):
        return self.globaldict

    def func_systemdict(self):
        return self.systemdict

    @stackify
    @staticmethod
    def func_put(d: dict, key, val):
        d[key] = val

    @stackify
    def func_forall(self, obj, proc):
        if isinstance(obj, list):
            for item in obj:
                self.append(item)
                self.run(proc)
        elif isinstance(obj, dict):
            for kv in obj.items():
                self.extend(kv)
                self.run(proc)
        else:
            raise

    @stackify
    def func_copy(self, d1, d2):
        d2.update(d1)
        return d2

    # Postscript specific stuff

    @stackify
    def func_exec(self, obj):
        """
        > /run { (r) file exec } def
        """
        if isinstance(obj, bytearray):
            return self.runfile(obj.decode())
        return self.runfile(obj.read())

    def func_quit(self):
        raise QuitException()

    @staticmethod
    def func_rand():
        import random
        return random.randint(0, 1 << 31)

    func_showpage = noop(0)

    @stackify
    @staticmethod
    def func_cvx(obj):
        if isinstance(obj, list):
            return Block(obj)
        return obj

    @stackify
    @staticmethod
    def func_array(l):
        return [None] * l

    @stackify
    @staticmethod
    def func_cvn(s):
        return Name(s.decode())

    #
    # Strings
    # strings are the one thing that ps doesn't map to python 1:1
    # have allocations

    @stackify
    @staticmethod
    def func_string(l):
        """
        Allocate string of length l
        """
        return bytearray(l)

    @stackify
    @staticmethod
    def func_cvs(obj, buf):
        s = str(obj).encode()
        buf[:len(s)] = s
        return bytearray(s)

    @stackify
    @staticmethod
    def func_length(obj):
        return len(obj)

    @stackify
    @staticmethod
    def func_putinterval(outerstr, offset, innerstr):
        outerstr[offset:offset + len(innerstr)] = innerstr

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

    def do_block(self, token):
        acc = []
        while True:
            if token.startswith('{'):
                token = yield from self.do_block(token[1:])
            elif token.endswith('}'):
                token = token[:-1]
                if token != '':
                    acc.append(token)
                break
            if token != '':
                acc.append(token)
            token = yield
        return Block(acc)

    def tokenize(self):
        while True:
            token = yield
            if isinstance(token, Block):
                # Do nothing
                self.append(token)
            elif token.isdigit() or token.startswith('-') and token[1:].isdigit():
                self.append(int(token))
            elif token.startswith('/'):
                self.append(Name(token[1:]))
            elif token.startswith('('):
                depth = 1
                acc = token
                if not token.endswith(')'):
                    while depth > 0:
                        token = yield
                        acc += ' ' + token
                        if token.startswith('('):
                            depth += 1
                        if token.endswith(')'):
                            depth -= 1
                self.append(bytearray(acc[1:-1].encode()))
            elif token.startswith('{'):
                b = yield from self.do_block(token[1:])
                self.append(b)
            else:
                self.dispatch_func(token)

    @staticmethod
    def lex(line: str):
        for word in line.split():
            if word.startswith('[') and len(word) > 1:
                yield word[:1]
                yield word[1:]
            elif word.endswith(']') and len(word) > 1 and word[-2] != '/':
                yield word[:-1]
                yield word[-1:]
            elif word.startswith('<<') and len(word) > 2:
                yield word[0:2]
                yield word[2:]
            elif word.endswith('>>') and len(word) > 2 and word[-3] != '/':
                yield word[:-2]
                yield word[-2:]
            else:
                yield word

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

    def runfile(self, lines):
        tokenizer = self.tokenize()
        next(tokenizer)

        for line in lines.splitlines():
            for word in line.split():
                if word == '%':
                    break
                tokenizer.send(word)

    def __call__(self, code: str):
        try:
            self.runfile(code)
        except QuitException:
            if self:
                print(f'warning, stack not empty on quit: {self}')

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
