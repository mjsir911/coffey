#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

# postscript parser

from typing import *
from inspect import isfunction

from functools import lru_cache
from collections import deque, UserString, UserList

from sys import argv


T = TypeVar('T')


@runtime_checkable
class Executable(Protocol[T]):
    def __call__(self, stack):
        ...


class ChildSlice(Generic[T]):
    parent: T
    slice: slice

    def __init__(self, backing_array: T, slice=slice(0, None)):
        self.parent = backing_array
        assert slice.step is None
        self.slice = slice

    @staticmethod
    def _constrain_slice(o, i):
        return slice(
            o.start + i.start if i.start is not None else o.start,
            o.start + i.stop if i.stop is not None else o.stop
        )

    def _add_slice(self, s):
        if isinstance(s, int):
            return self.slice.start + s
        # assert (self.slice.stop is None) == (s.stop is None), breakpoint()
        # return self._constrain_slice(self.slice,
        return slice(
            self.slice.start + (s.start if s.start is not None else 0),
            self.slice.start + s.stop if s.stop is not None else None
        )

    def __hash__(self):
        return hash(tuple(self))

    def __getitem__(self, index):
        cls = type(self)
        off_index = self._add_slice(index)
        if isinstance(index, int):
            return self.parent[index]
        elif off_index.start == 0 and off_index.stop is None:
            return self
        return cls(self, index)

    def __setitem__(self, index, value):
        index = self._add_slice(index)
        self.parent[index] = value

    def __iter__(self):
        return iter(self._unwrap())

    def __len__(self):
        return (self.slice.stop or len(self.parent)) - self.slice.start

    def _unwrap(self):
        p = self.parent
        if isinstance(self.parent, ChildSlice):
            p = p._unwrap()
        return p[self.slice]

    def __repr__(self):
        return repr(self._unwrap())

    def __str__(self):
        return str(self._unwrap())

    @property
    def data(self):
        return self._unwrap()


class String(ChildSlice[bytearray], UserString):
    def __init__(self, back, *args, **kwargs):
        if isinstance(back, str):
            back = bytearray(back.encode())
        super().__init__(back, *args, **kwargs)

    def __setitem__(self, index, value):
        index = self._add_slice(index)
        # Gotta do this since bytearray set checks for string type
        if isinstance(value, type(self)):
            value = iter(value)
        if isinstance(value, Name):
            breakpoint()
        self.parent[index] = iter(value)

    def __repr__(self):
        return '(' + repr(self._unwrap().decode())[1:-1] + ')'

    def __str__(self):
        return self._unwrap().decode()

    @property
    def data(self):
        return super().data.decode()


class ExecutableString(String, Executable[String]):
    def __call__(self, stack):
        stack.run(stack.parse(deque(stack.lex(self))))
        return ()


class Array(ChildSlice[list], UserList):
    pass


class ExecutableArray(Array, Executable[Array]):
    def __call__(self, stack):
        stack.run(self)
        return ()

    def __repr__(self):
        return f'{{{" ".join(str(item) for item in self)}}}'


class Name(str):
    def __repr__(self):
        return '/' + super().__str__()


class ExecutableName(Name, Executable[Name]):
    def __call__(self, stack):
        a = stack.get_func(self)
        if isinstance(a, Executable):
            return a(stack)
        return (a,)

    def __repr__(self):
        return super().__str__()


markStart = object()


def noop(n):
    def wrapper(stack):
        for _ in range(n):
            stack.pop()
    return wrapper


class QuitException(Exception):
    pass


class ExitException(Exception):
    pass


class Runner(list):
    """
    > globaldict /def { globaldict 3 1 roll put } put
    > /cleartomark { unmark pop } def
    """
    globaldict: Dict[str, callable]
    systemdict: Dict[str, Any]

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

        stream = deque()
        for line in self.prelude():
            stream.extend(self.lex(line))

        self.run(self.parse(stream))

    def run(self, code):
        code = list(code)
        for thing in code:
            if isinstance(thing, ExecutableName):
                a = thing(self)
                self.extend(a)
            else:
                self.append(thing)

    def stackify(unbound_func):
        from functools import wraps
        from inspect import signature

        # bleh
        @wraps(unbound_func.__get__(int))
        def wrapper(self):
            func = unbound_func.__get__(self)
            numargs = len(signature(func).parameters)
            if len(self) < numargs:
                breakpoint()
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

    @stackify
    @staticmethod
    def func_and(a, b):
        return a and b

    @stackify
    @staticmethod
    def func_or(a, b):
        return a | b

    @stackify
    @staticmethod
    def func_min(a, b):
        return a if a < b else b

    @stackify
    @staticmethod
    def func_neg(a):
        return -a

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
        print(repr(a))

    def func_stack(self):
        for thing in reversed(self):
            self.append(thing)
            self.func_hex_3D()

    def func_pstack(self):
        for thing in reversed(self):
            self.append(thing)
            self.func_hex_3D3D()

    def func_breakpoint(self):
        breakpoint()

    #
    # IO

    @stackify
    @staticmethod
    def func_file(fname, mode):
        return (open(str(fname), str(mode)),)

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
        return Array(ret)

    def func_counttomark(self):
        return self[::-1].index(markStart)

    def func_hex_3E3E(self):
        " >> "
        b = self.func_unmark()
        if len(b) > 0 and isinstance(b[0], dict):
            breakpoint()
        l = iter(b)
        return dict(zip(l, l))

    #
    # Dictionary functions

    def func_globaldict(self):
        return self.globaldict

    def func_systemdict(self):
        return self.systemdict

    @stackify
    @staticmethod
    def func_put(d: Union[dict, list], key, val):
        d[key] = val

    @stackify
    @staticmethod
    def func_get(d: dict, key):
        return (d[key],)

    @stackify
    def func_astore(self, l: list):
        self.extend(l)

    @stackify
    def func_forall(self, obj, proc):
        if isinstance(obj, (list, UserList)):
            it = ((i,) for i in obj)
        elif isinstance(obj, dict):
            it = obj.items()
        else:
            breakpoint()
            raise TypeError(obj)

        for items in it:
            self.extend(items)
            self.run(proc)

    @stackify
    @staticmethod
    def func_known(d: dict, k):
        return k in d

    #
    # Array functions

    @stackify
    @staticmethod
    def func_getinterval(array, start, end):
        return array[start:start + end]

    @stackify
    @staticmethod
    def func_not(b: bool):
        return not b

    @stackify
    def func_ifelse(self, cond: bool, a: Executable, b: Executable):
        """
        > /if { {} ifelse } def
        """
        if cond:
            return a(self)
        else:
            return b(self)

    @stackify
    def func_loop(self, block: Executable):
        while True:
            try:
                block(self)
            except ExitException:
                break

    @staticmethod
    def func_exit():
        raise ExitException("exit")

    @staticmethod
    def func_null():
        return (None,)

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
        if isinstance(obj, Executable):
            return obj(self)
        return self.runlines(obj.read())

    def func_quit(self):
        raise QuitException()

    @stackify
    @staticmethod
    def func_cvlit(obj: Executable[T]) -> T:
        if isinstance(obj, ExecutableArray):
            return Array(obj)
        elif isinstance(obj, ExecutableName):
            return Name(obj)
        else:
            raise TypeError(type(obj))

    @staticmethod
    def func_rand():
        import random
        return random.randint(0, 1 << 31)

    func_showpage = noop(0)

    @stackify
    @staticmethod
    def func_type(thing):
        if isinstance(thing, Name):
            return Name('nametype')
        if isinstance(thing, (str, bytearray, UserString)):
            return Name('stringtype')
        elif isinstance(thing, int):
            return Name('integertype')
        elif isinstance(thing, (list, Array)):
            return Name('arraytype')
        elif isinstance(thing, type(None)):
            return Name('nulltype')
        else:
            raise TypeError(type(thing))

    @stackify
    @staticmethod
    def func_eq(a, b):
        return a == b

    @stackify
    @staticmethod
    def func_cvx(obj: T) -> Executable[T]:
        if isinstance(obj, Array):
            return ExecutableArray(obj)
        elif isinstance(obj, Name):
            return ExecutableName(obj)
        elif isinstance(obj, String):
            return ExecutableString(obj)
        else:
            raise TypeError(type(obj))

    @stackify
    @staticmethod
    def func_xcheck(obj: Union[T, Executable[T]]):
        return isinstance(obj, Executable)

    @stackify
    @staticmethod
    def func_signalerror(something):
        raise Exception(something)

    @stackify
    @staticmethod
    def func_array(l):
        return Array([None] * l)

    @stackify
    @staticmethod
    def func_cvn(s):
        return Name(s)

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
        return String(bytearray(l))

    @stackify
    @staticmethod
    def func_cvs(obj, buf):
        s = str(obj).encode()
        l = len(s)
        ret = String(buf, slice(0, l))
        ret[:l] = s
        # print(repr(ret))
        return ret

    @stackify
    @staticmethod
    def func_length(obj):
        return len(obj)

    @stackify
    @staticmethod
    def func_putinterval(outer, offset, inner):
        outer[offset:offset + len(inner)] = inner

    def get_func(self, funcname):
        if funcname not in self.systemdict:
            func = self.globaldict[funcname]
            return func
        func = self.systemdict[funcname]

        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            ret = func()
            if ret is None:
                return ()
            if not isinstance(ret, (tuple, Iterator)):
                ret = (ret,)
            return ret
        return wrapper

    def do_block(self, stream):
        acc = []
        while stream:
            token = stream.popleft()
            if token.startswith('{'):
                stream.appendleft(token[1:])
                acc.append(self.do_block(stream))
            elif token.endswith('}'):
                token = token[:-1]
                if token != '':
                    # this is gonna cause problems
                    acc.extend(list(self.parse(deque([token]))))
                    # acc.append(token)
                break
            elif token != '':
                stream.appendleft(token)
                acc.extend(list(self.parse(stream, False)))
        return ExecutableArray(acc)

    def parse(self, stream, consume=True):
        while stream:
            token = stream.popleft()
            if isinstance(token, Array):
                # Do nothing
                yield token
            elif token.isdigit() or token.startswith('-') and token[1:].isdigit():
                yield int(token)
            elif token.startswith('/'):
                yield Name(token[1:])
            elif token.startswith('('):
                # this should all move to lex
                acc = token[0]
                depth = 1
                stream.appendleft(token[1:])
                while depth > 0:
                    line = deque(stream.popleft())
                    while line:
                        char = line.popleft()
                        if char == '\\':  # this will break on \ before newline
                            acc += line.popleft()
                            continue
                        if char == '(':
                            depth += 1
                        elif char == ')':
                            depth -= 1
                        acc += char
                    acc += ' '
                yield String(acc[1:-2])

                # acc = token
                # if not token.endswith(')'):
                #     # This is currently very broken
                #     while depth > 0:
                #         token = stream.popleft()
                #         token = token.replace('\\', '')
                #         acc += ' ' + token
                #         if token.startswith('('):
                #             depth += 1
                #         if token.endswith(')'):
                #             depth -= 1
                # yield String(bytearray(acc[1:-1].encode()))
            elif token.startswith('{'):
                stream.appendleft(token[1:])
                yield self.do_block(stream)
            else:
                yield ExecutableName(token)
                # yield from self.dispatch_func(token)
            if not consume:
                break

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

    def runline(self, line):
        self.run(self.parse(deque(self.lex(line))))

    def runlines(self, lines):
        stream = deque()
        for line in lines.splitlines():
            for word in self.lex(line):
                if word == '%':
                    break
                stream.append(word)

        self.run(self.parse(stream))

    def __call__(self, code: str):
        try:
            self.runlines(code)
        except QuitException:
            if self:
                # print(f'warning, stack not empty on quit: {self}')
                pass

        return self


if __name__ == '__main__':
    r = Runner()
    if len(argv) > 1:
        print(r(open(argv[1]).read()))
    else:
        print(r.globaldict.keys())
        while True:
            r(input('> '))
        # import rlcompleter
        # import readline
        # readline.set_completer(print)
        # readline.parse_and_bind("tab: complete")
        # input('$')
