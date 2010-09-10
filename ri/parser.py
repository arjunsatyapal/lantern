"""Minimum "parser" replacement for AppEngine Environment

The interactive environment wants to know if a user input is a
complete Python stmt/expr by using parser.suite() and parser.expr().

This module emulates parser module that is unavailable in the
AppEngine environment by actually trying to run the user input in a
restricted environment to see if we get a syntax error; in order to
prevent an actual execution from contaminating the global environment,
standard streams are removed during the execution of these functions,
and no builtin is made available.
"""

import sys
__ns = {
    "__builtins__": { "nothing": "4U" }
}

def suite(line):
  try:
    save = (sys.stdin, sys.stdout, sys.stderr)
    sys.stdin = sys.stdout = sys.stderr = None
    try:
      exec line in __ns
    except SyntaxError:
      raise
    except:
      pass
  finally:
    (sys.stdin, sys.stdout, sys.stderr) = save

def expr(line):
  try:
    save = (sys.stdin, sys.stdout, sys.stderr)
    sys.stdin = sys.stdout = sys.stderr = None
    try:
      eval(line, __ns)
    except SyntaxError:
      raise
    except:
      pass
  finally:
    (sys.stdin, sys.stdout, sys.stderr) = save
