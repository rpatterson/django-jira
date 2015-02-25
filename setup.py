import os

from distutils.core import setup

setup(name='django-jira',
      version='2.2',
      description='An automated exception reporter to JIRA from Django',
      long_description=open(
          "README.rst").read() + "\n" + open(
              os.path.join("docs", "HISTORY.txt")).read(),
      author='Stephen Golub',
      author_email='nickburns2006@tamu.edu',
      url='https://github.com/nickburns2006/django-jira',
      packages=['django_jira'],
      install_requires=['jira-python', 'django>=1.4'],
      )
