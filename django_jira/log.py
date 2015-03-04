import logging
import re
import sys
import traceback


from django.utils.log import AdminEmailHandler
from django.views.debug import get_exception_reporter_filter

from jira.client import JIRA


class JiraRecord(object):

    def __init__(self, record, exc_info):
        self.request = getattr(record, 'request', None)
        self.exc_info = exc_info
        self.levelname = "ERROR"

    def getMessage(self):
        return "Problem Working with Jira Server"


class JiraHandler(logging.Handler):

    """An exception log handler that sends the log entries to the specified
    Jira server and project.

    If the request is passed as the first arguemtn to the log record, request
    data will be provided in the Jira Ticket.

    """

    colors = (
        'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
    color_codes = {str(code): color for code, color in enumerate(colors)}
    color_pattern = re.compile('(?ms)(\\x1b\\[1;3([0-7])m(.*)\\x1b\\[0m|.*)')

    def __init__(
            self, include_html=False, server_url="http://localhost:2990/jira/",
            user=False, password=False, auth_type=None, issue_defaults=False,
            reopen_closed=(4, 6), reopen_action=3, wont_fix=False,
            comment_reopen_only=False, mail_logger="mail_admins",
            no_view_full_stack=False):
        logging.Handler.__init__(self)
        self.include_html = include_html
        if not server_url or not user or not password:
            self.unused = True
        else:
            self.unused = False
            self.jira_url = server_url
            self.jira_user = user
            self.jira_pwd = password
            self.auth_type = auth_type

            if issue_defaults:
                self.issue_defaults = issue_defaults.copy()
            else:
                self.issue_defaults = {}

            if 'project' not in self.issue_defaults:
                self.issue_defaults['project'] = {'key': 'JIRA'}
            elif not isinstance(self.issue_defaults['project'], dict):
                self.issue_defaults['project'] = {
                    'key': self.issue_defaults['project']}

            if 'issuetype' not in self.issue_defaults:
                self.issue_defaults['issuetype'] = {'id': '1'}
            elif not isinstance(self.issue_defaults['issuetype'], dict):
                self.issue_defaults['issuetype'] = {
                    'id': self.issue_defaults['issuetype']}

            self.reopen_closed = reopen_closed
            self.reopen_action = reopen_action
            self.wont_fix = wont_fix
            self.comment_reopen_only = comment_reopen_only
            self.mail_logger = mail_logger

            self.no_view_full_stack = no_view_full_stack

    @property
    def _jira(self):
        if not isinstance(getattr(self, '_jr', None), JIRA):
            if (
                    hasattr(self, "jira_url") and hasattr(self, "jira_user")
                    and hasattr(self, "jira_pwd")):
                auth_type = getattr(self, "auth_type", "basic").lower()

                if auth_type is None:
                    self._jr = JIRA(options={"server": self.jira_url})
                elif auth_type == "basic":
                    self._jr = JIRA(
                        basic_auth=(self.jira_user, self.jira_pwd),
                        options={"server": self.jira_url})
                elif auth_type == "oauth":
                    raise NotImplementedError(
                        "OAuth for the Jira Reporter hasn't been implemented yet.")
                else:
                    raise Exception("You have entered an invalid AuthType")
            else:
                raise Exception("There is a problem with the configuration of the django-jira app.")
        return self._jr

    def fire_email(self, record, exc_info=None):
        mail_handler = AdminEmailHandler(include_html=self.include_html)
        mail_handler.emit(record)
        mail_handler.emit(JiraRecord(record, exc_info))

    def emit(self, record):
        if self.unused:
            self.fire_email(record)

        try:
            self._emit(record)
        except Exception:
            return self.fire_email(record, sys.exc_info())

    def _emit(self, record):
        # We're first going to construct the strings
        issue_title = issue_msg = record.getMessage()
        stack_trace = None
        request = getattr(record, 'request', None)
        full_stack = getattr(record, 'full_stack', False)

        try:
            # Find the view for this request
            # From django.core.handlers.base:BaseHandler.get_response
            from django.core import urlresolvers
            from django.conf import settings

            urlconf = settings.ROOT_URLCONF
            urlresolvers.set_urlconf(urlconf)
            resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)
            callback, callback_args, callback_kwargs = resolver.resolve(
                request.path_info)
            caller = '{0}:{1}'.format(
                callback.__module__, callback.__name__)
        except Exception:
            caller = None
            if self.no_view_full_stack:
                full_stack = True

        if record.exc_info:
            exc_info = record.exc_info

            if caller is None:
                # This parses the traceback - so we can get the name of the function
                # which generated this exception
                exc_tb = traceback.extract_tb(exc_info[2])
                caller = exc_tb[-1][2]

            exc_type = type(exc_info[1]).__name__
            issue_title = re.sub(
                r'"', r'\\\"', exc_type + ' thrown by ' + caller)

            if full_stack:
                stack_trace = (
                    'Traceback (most recent call last):\n{0}'.format(
                        ''.join(
                            traceback.format_stack(exc_info[2].tb_frame) +
                            traceback.format_exception_only(*exc_info[:2]))))
            else:
                stack_trace = ''.join(
                    traceback.format_exception(*record.exc_info))
        elif full_stack:
            caller_info = logging.getLogger(record.name).findCaller()
            frame = logging.currentframe()
            while frame and (
                    frame.f_code.co_filename,
                    frame.f_lineno,
                    frame.f_code.co_name) != caller_info:
                frame = frame.f_back
            stack_trace = 'Traceback (most recent call last):\n{0}'.format(
                ''.join(traceback.format_stack(frame)))

        if stack_trace:
            issue_msg += '\n\n{code:title=Traceback}\n%s\n{code}' % (
                stack_trace)

        if request:
            filter = get_exception_reporter_filter(request)
            request_repr = filter.get_request_repr(request)
            issue_msg += '\n\n{code:title=Request}\n%s\n{code}' % request_repr

        # Convert ASCII color codes to the Jira text effect
        issue_msg = ''.join(
            match.group(2) in self.color_codes and
            '\n{{color:{0}}}\n{1}\n{{color}}'.format(
                self.color_codes[match.group(2)], match.group(3)
            ) or match.group(0)
            for match in self.color_pattern.finditer(issue_msg)).lstrip('\n')

        # See if this exception has already been reported inside JIRA
        existing = self._jira.search_issues(
            'project = "' + self.issue_defaults['project']["key"] +
            '" AND summary ~ "\\"' + issue_title + '\\""', maxResults=1)

        # If it has, add a comment noting that we've had another report of it
        found = False
        for issue in existing:
            if issue_title == issue.fields.summary:

                # If this issue is closed, reopen it
                if int(issue.fields.status.id) in self.reopen_closed \
                        and (issue.fields.resolution and int(issue.fields.resolution.id) != self.wont_fix):
                    self._jira.transition_issue(
                        issue, str(self.reopen_action))

                    reopened = True
                else:
                    reopened = False

                # Add a comment
                if reopened or not self.comment_reopen_only:
                    self._jira.add_comment(issue, issue_msg)

                found = True
                break

        if not found:
            # Otherwise, create it
            issue = self.issue_defaults.copy()
            issue['summary'] = issue_title
            issue['description'] = issue_msg

            self._jira.create_issue(fields=issue)
