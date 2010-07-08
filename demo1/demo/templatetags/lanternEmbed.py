from django.template.defaultfilters import stringfilter
from django import template
register = template.Library()

def PYTHON_INTERPRETER():
  return '''<iframe src ="http://pyshell1.appspot.com/pyshell" width="100%" height="300">
  <p>Your browser does not support iframes.</p>
</iframe>'''

def MULTIPLE_CHOICE_QUIZ(token):
  return '<!-- Multiple choice quiz %s here -->' % token

@register.filter(name='lanternEmbed')
@stringfilter
def lanternEmbed(value):
  """Add python interpreter and other links to a Lantern doc template"""

  result = []
  while 1:
    pos = value.find('$$')
    if pos < 0:
      break
    tail = value.find('$$', pos+2)
    if tail < 0:
      break

    result.append(value[0:pos])
    meat, value = value[pos+2:tail], value[tail+2:]
    try:
      it = eval(meat)
      result.append(it)
    except:
      pass

  result.append(value)
  return "".join(result)
