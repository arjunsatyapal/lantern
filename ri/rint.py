#!/usr/bin/python2.4 -tt

import os

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db

import ri

class SoFar(db.Model):
  input_so_far = db.TextProperty()
  last_state = db.IntegerProperty()

class MainPage(webapp.RequestHandler):

  def _doit(self):

    if self.request.get('edit'):
      return self._edit()

    program = self.request.get('program')
    sofar = self.request.get('sofar')
    interp_state = 0
    if sofar:
      state = SoFar.get_or_insert(sofar, input_so_far='', last_state=0)
      if program:
        program = program.replace("\r\n", "\n")
        state.input_so_far = program
        if state.input_so_far[-1:] != "\n":
          state.input_so_far += "\n"
      else:
        newline = self.request.get('input')
        if newline != "" or state.last_state == 1:
          state.input_so_far += newline + "\n"

      interp = ri.ReplayInterpreter(state.input_so_far)
      output_so_far = interp.run()
      interp_state = interp.state
    else:
      interp_state = -1
      state = SoFar()
      state.input_so_far = ""
      state.put()
      sofar = state.key().name()
      output_so_far = ""

    if interp_state < 0:
      output_so_far += "\n>>>"
      interp_state = 0
    elif interp_state <= 1:
      pass
    elif interp_state == 2:
      output_so_far += "\n"
    elif interp_state == 3:
      output_so_far += "\n***BYE***"

    state.last_state = interp_state
    state.put()

    template_values = {
        'sofar': sofar,
        'output': output_so_far,
        'input_so_far': state.input_so_far,
        'alive': interp_state != 3,
        }

    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))

  def _edit(self):
    sofar = self.request.get('sofar')
    interp_state = 0
    if sofar:
      state = SoFar.get_or_insert(sofar, input_so_far='', last_state=0)
      while state.input_so_far[-2:] == "\n\n":
        state.input_so_far = state.input_so_far[:-1]
    else:
      state = SoFar()
      state.input_so_far = ""
      state.put()
      sofar = state.key().name()

    template_values = {
        'sofar': sofar,
        'input_so_far': state.input_so_far,
    }
    path = os.path.join(os.path.dirname(__file__), 'edit.html')
    self.response.out.write(template.render(path, template_values))

  def get(self):
    self._doit()

  def post(self):
    self._doit()

class Blank(webapp.RequestHandler):
  
  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'blank.html')
    self.response.out.write(template.render(path, {}))

class Relay(webapp.RequestHandler):

  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'relay.html')
    self.response.out.write(template.render(path, {}))

application = webapp.WSGIApplication([('/', MainPage),
                                      ('/blank.html', Blank),
                                      ('/relay.html', Relay)],
                                     debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
