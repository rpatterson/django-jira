from distutils.core import setup

setup(name='django-jira',
      version='2.1',
      description='An automated exception reporter to JIRA from Django',
      author='Stephen Golub',
      author_email='nickburns2006@tamu.edu',
      url='https://github.com/nickburns2006/django-jira',
      packages=['django_jira'],
      install_requires=['jira-python',],
     )
