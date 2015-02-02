#!/usr/bin/env python

from StringIO import StringIO
from tokenize import *
import string
import sys

class Stack:
    def __init__(self):
        self._values = []

    def pop(self):
        if len(self._values) == 0:
            raise RuntimeError("Stack underflow")
        return self._values.pop()

    def push(self, value):
        self._values.append(value)

    @property
    def top(self):
        return self._values[-1]


class Machine:
    def __init__(self, code, stdout=sys.stdout):
        self.data_stack = Stack()
        self.return_stack = Stack()
        self.instruction_pointer = 0
        self.code = code
        self.stdout = stdout

        self.dispatch_map = {
            "%":        self.mod,
            "*":        self.mul,
            "+":        self.add,
            "-":        self.sub,
            ".":        self.dot,
            "/":        self.div,
            "<":        self.less,
            "==":       self.eq,
            ">":        self.greater,
            "@":        self.at,
            "add":      self.add,
            "call":     self.call,
            "cast_int": self.cast_int,
            "cast_str": self.cast_str,
            "div":      self.div,
            "drop":     self.drop,
            "dup":      self.dup,
            "exit":     self.exit,
            "false":    self.false_,
            "if":       self.if_stmt,
            "jmp":      self.jmp,
            "mod":      self.mod,
            "mul":      self.mul,
            "over":     self.over,
            "read":     self.read,
            "return":   self.return_,
            "stack":    self.dump_stack,
            "sub":      self.sub,
            "swap":     self.swap,
            "true":     self.true_,
            "write":    self.write,
        }

    @property
    def stack(self):
        """Returns the data (operand) stack values."""
        return self.data_stack._values

    def pop(self):
        return self.data_stack.pop()

    def push(self, value):
        self.data_stack.push(value)

    @property
    def top(self):
        return self.data_stack.top

    def run(self):
        try:
            while self.instruction_pointer < len(self.code):
                opcode = self.code[self.instruction_pointer]
                self.instruction_pointer += 1
                self.dispatch(opcode)
            return self
        except StopIteration:
            pass
        except EOFError:
            pass

    def dispatch(self, op):
        if op in self.dispatch_map:
            self.dispatch_map[op]()
        else:
            if isinstance(op, int):
                self.push(op) # push numbers on stack
            elif isinstance(op, str) and op[0]==op[-1]=='"':
                self.push(op[1:-1]) # push quoted strings on stack
            else:
                raise RuntimeError("Unknown opcode: '%s'" % op)

    # OPERATIONS FOLLOW:

    def add(self):
        self.push(self.pop() + self.pop())

    def sub(self):
        last = self.pop()
        self.push(self.pop() - last)

    def call(self):
        self.return_stack.push(self.instruction_pointer)
        self.jmp()

    def return_(self):
        self.instruction_pointer = self.return_stack.pop()

    def mul(self):
        self.push(self.pop() * self.pop())

    def div(self):
        last = self.pop()
        self.push(self.pop() / last)

    def mod(self):
        last = self.pop()
        self.push(self.pop() % last)

    def exit(self):
        raise StopIteration

    def dup(self):
        a = self.pop()
        self.push(a)
        self.push(a)

    def over(self):
        b = self.pop()
        a = self.pop()
        self.push(a)
        self.push(b)
        self.push(a)

    def drop(self):
        self.pop()

    def swap(self):
        b = self.pop()
        a = self.pop()
        self.push(b)
        self.push(a)

    def write(self):
        self.stdout.write(str(self.pop()))
        self.stdout.flush()

    def at(self):
        self.return_stack.push(self.instruction_pointer - 1)

    def dot(self):
        self.write()
        self.stdout.write("\n")
        self.stdout.flush()

    def read(self):
        self.push(raw_input())

    def cast_int(self):
        self.push(int(self.pop()))

    def cast_str(self):
        self.push(str(self.pop()))

    def eq(self):
        self.push(self.pop() == self.pop())

    def less(self):
        a = self.pop()
        self.push(a < self.pop())

    def greater(self):
        a = self.pop()
        self.push(a > self.pop())

    def true_(self):
        self.push(True)

    def false_(self):
        self.push(False)

    def if_stmt(self):
        false_clause = self.pop()
        true_clause = self.pop()
        test = self.pop()

        # False values: False, 0, "", everyting else is true
        if isinstance(test, bool) and test == False:
            result = False
        elif isinstance(test, str) and len(test) == 0:
            result = False
        elif isinstance(test, int) and test == 0:
            result = False
        else:
            result = True

        if result == True:
            self.push(true_clause)
        else:
            self.push(false_clause)

    def jmp(self):
        addr = self.pop()
        if isinstance(addr, int) and addr >= 0 and addr < len(self.code):
            self.instruction_pointer = addr
        else:
            raise RuntimError("JMP address must be a valid integer.")

    def dump_stack(self):
        self.stdout.write("Data stack:\n")
        for v in reversed(self.data_stack._values):
            self.stdout.write(" - type %s, value '%s'\n" % (type(v), v))

        self.stdout.write("Return stack:\n")
        for v in reversed(self.return_stack._values):
            self.stdout.write(" - address %s\n" % str(v))

        self.stdout.flush()

def parse(stream):

    code = []
    tokens = generate_tokens(stream.readline)

    def strip_whitespace(s):
        r = ""
        for ch in s:
            if not ch in string.whitespace:
                r += ch
            else:
                r += "\\x%x" % ord(ch)
        return r

    while True:
        for token, value, _, _, _ in tokens:
            if token == NUMBER:
                code.append(int(value))
            elif token in [OP, STRING, NAME]:
                code.append(value)
            elif token in [NEWLINE, NL]:
                break
            elif token in [COMMENT, INDENT, DEDENT]:
                pass
            elif token == ENDMARKER:
                return code
            else:
                raise RuntimeError("Unknown token %s: '%s'" %
                        (tok_name[token], strip_whitespace(value)))
    return code

def translate(code, dump_source=False):
    """Translates stuff such as subroutines etc into a complete working
    code."""

    output = []
    subroutine = {}
    builtins = Machine([]).dispatch_map

    try:
        it = code.__iter__()
        while True:
            word = it.next()
            if word == ":":
                name = it.next()
                if name in builtins:
                    raise RuntimeError("Cannot shadow internal word definition '%s'." % name)
                if name in [":", ";"]:
                    raise RuntimeError("Invalid word name '%s'." % name)
                subroutine[name] = []
                while True:
                    op = it.next()
                    if op == ";":
                        subroutine[name].append("return")
                        break
                    else:
                        subroutine[name].append(op)
            else:
                output.append(word)
    except StopIteration:
        pass

    # Expand all subroutine words to ["<name>", "call"]
    for name, code in subroutine.items():
        # For subroutines
        xcode = []
        for op in code:
            xcode.append(op)
            if op in subroutine:
                xcode.append("call")
        subroutine[name] = xcode

    xcode = []
    for op in output:
        xcode.append(op)
        if op in subroutine:
            xcode.append("call")
    output = xcode + ["exit"]

    # Add subroutines to output, track their locations
    location = {}
    for name, code in subroutine.items():
        location[name] = len(output)
        output += code

    # Resolve all subroutine references
    for i, op in enumerate(output):
        if op in location:
            output[i] = location[op]

    if dump_source:
        revloc = dict(((b,a) for a,b in location.items()))
        prev = None
        width = len(str(len(output)))
        for i, op in enumerate(output):
            if i in revloc:
                name = revloc[i]
                print("\n%s:" % name)
            if op == "call":
                print("  %.*d %s (%s)" % (width, i, op, revloc[prev]))
            else:
                print("  %.*d %s" % (width, i, op))
            prev = op

    return output

def constant_fold(code, silent=True):
    """Constant-folds simple expressions like 2 3 + to 5."""

    # Loop until we haven't done any optimizations.  E.g., "2 3 + 5 *" will be
    # optimized to "5 5 *" and in the next iteration to 25.

    arithmetic = ["+", "-", "*", "/", "%", "add", "sub", "mul", "div", "mod"]

    keep_running = True
    while keep_running:
        keep_running = False
        # Find two consecutive numbes and an arithmetic operator
        for i, ops in enumerate(zip(code, code[1:], code[2:])):
            a, b, op = ops
            if type(a)==type(b)==int and op in arithmetic:
                result = Machine(ops).run().top
                del code[i:i+3]
                code.insert(i, result)
                keep_running = True
                if not silent:
                    print("Optimizer: Constant-folded %d %s %d to %d" % (a,op,b,result))
                break
    return code

def repl(optimize=True):
    while True:
        try:
            source = raw_input("> ")
            code = translate(parse(StringIO(source)))
            if optimize:
                code = constant_fold(code, silent=False)
            Machine(code).run()
        except EOFError:
            return
        except KeyboardInterrupt:
            return
        except Exception, e:
            print("Error: %s" % e)

if __name__ == "__main__":
    try:
        if len(sys.argv) == 1:
            repl()
            sys.exit(0)

        dump_source = False

        for name in sys.argv[1:]:
            with open(name, "rt") as file:
                Machine(translate(parse(file), dump_source)).run()

    except KeyboardInterrupt:
        pass