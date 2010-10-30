#!/usr/bin/python2.4 -tt
"""Replaying Interpreter

Program state, kept in the database (pickled):
 - initialization (python code)
 - previously read input;
 - "fake" filesystem environment (later);

Flow:
 - Read the "current" state;
 - Feed the previously read input to the interpreter,
   stop at the input request;
 - Keep the current state;
 - Emit the new output;
 - Exit

"""

import pickle
import parser
import sys
import StringIO


class NeedMoreInputException(Exception):
  pass


class RIinput(StringIO.StringIO):
  def __init__(self, echo):
    StringIO.StringIO.__init__(self)
    self.__echo = echo

  def append(self, data):
    """Stuff data to be returned by further read(), readline(), etc."""
    self.buflist.append(data.encode('utf-8'))

  def readline(self, length=None):
    l = StringIO.StringIO.readline(self, length)
    if l == "":
      raise NeedMoreInputException
    if self.__echo:
      self.__echo(l)
    return l


def CreateCustomNamespace():
  """Namespace for sandbox environment"""
  ns = dict()
  try:
    builtin_dict = __builtins__.__dict__
  except AttributeError:
    builtin_dict = __builtins__
  ns["__builtins__"] = builtin_dict.copy()
  ns["sys"] = sys
  return ns


class ReplayInterpreter(object):
  """Execute python program in a sandbox"""

  def __init__(self, input="", init=""):
    self.__init = init
    self.reset()
    self.__input = input

  def reset(self):
    self.__input = None
    self.__ns = CreateCustomNamespace()

    # Run the initialization code, throwing possible exceptions
    # back at the caller
    exec self.__init in self.__ns

  def _fini(self):
    self.state = 3
    raise SystemExit

  def __run(self):
    """Python Interpreter REPL"""

    ns = self.__ns
    line = ""

    while 1:

      if line == "":
        print ">>>",
        self.state = 0  # waiting for a command
      else:
        print "..",
        self.state = 1  # waiting for the rest of the command

      add = sys.stdin.readline()

      if add != "":
        if line == "":
          # Try compiling it
          line = add
          try:
            st = parser.suite(line)
          except SyntaxError:
            continue
        else:
          # An empty line splits the input
          if add != "\n":
            line += add
            continue
      elif line == "":
        return

      # We have a complete input in "line"
      try:
        # Is it an expression?
        st = parser.expr(line)
        is_expression = True
      except SyntaxError:
        is_expression = False

      try:
        # Execute the user code...
        self.state = 2  # executing the user code
        if is_expression:
          value = eval(line, ns)
          if value is not None:
            print "%s" % value
            ns["_"] = value
        else:
          exec line in ns
        line = ""
      except NeedMoreInputException:
        # The user code reads from stdin...
        raise
      except SystemExit:
        self._fini()
      except Exception, e:
        print "MyError: %s" % e
      line = ""

  def echo(self, line):
    while line[-1:] == '\n':
      line = line[:-1]
    print >>sys.stdout, line

  def run(self):

    self.old_stdin = sys.stdin
    self.old_stdout = sys.stdout
    self.old_stderr = sys.stderr

    try:
      stdout = StringIO.StringIO()
      sys.stdout = stdout
      sys.stderr = stdout
      sys.stdin = RIinput(self.echo)
      if self.__input:
        for l in "".join(self.__input).split("\n")[:-1]:
          sys.stdin.append(l + "\n")

      # Run the user code in the sandbox
      try:
        self.__run()
      except (NeedMoreInputException, SystemExit):
        pass

    finally:
      sys.stdin = self.old_stdin
      sys.stdout = self.old_stdout
      sys.stderr = self.old_stderr

    return stdout.getvalue()

if __name__ == "__main__":
  class AccumulatingReplayInterpreter(object):

    def __init__(self):
      self.input_so_far = ""

    def run(self, str):
      if str[-1:] != "\n":
        str += "\n"
      self.input_so_far += str
      self.ri = ReplayInterpreter(self.input_so_far)
      return self.ri.run()

  ai = AccumulatingReplayInterpreter()

  def runit(str):
    print ai.run(str)
    print "*status*", ai.ri.state
    print "----------------------------------------------------------------"
    sys.stdout.flush()

  runit("min(123, 234)")
  if 1:
   runit("sys.stdout.write('%s\\n' % max(123, 234))")

   runit("""def sumto(x):
   if x == 0:
     return 0
   else:
     return sumto(x-1) + x

sumto(4)
x = 4
x += 10
x
""")

   runit("x = sys.stdin.readline()\n")
   runit("all the fish\n")

   runit("print 'Thanks for %s' % x[:-1]\n")
   runit("print 'Almost done.'\n")
   runit("print 'All done.'\n")
