import os

from distutils.core import setup

setup(name='django-jira',
      version='2.2',
      description='An automated exception reporter to JIRA from Django',
      long_description=open(
          "README.rst").read() + "\n" + open(
              os.path.join("docs", "HISTORY.txt")).read(),
      author='Ross Patterson',
      author_email='me@rpatterson.net',
      url='https://github.com/rpatterson/django-jira',
      packages=['django_jira'],
      install_requires=['jira-python', 'django>=1.4'],
      )
