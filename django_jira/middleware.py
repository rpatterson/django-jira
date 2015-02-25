import traceback
import sys
import re

from django.conf import settings
from django.http import Http404
from django.core.exceptions import MiddlewareNotUsed

from jira.client import JIRA
from jira.exceptions import JIRAError


class JiraExceptionReporterMiddleware:

    def __init__(self):

        # If we're in debug mode, and JIRA_REPORT_IN_DEBUG is false (or not set)
        # then don't report errors
        if settings.DEBUG:
            try:
                if not settings.JIRA_REPORT_IN_DEBUG:
                    raise MiddlewareNotUsed
            except AttributeError:
                raise MiddlewareNotUsed

        # Silently fail if any settings are missing
        try:
            settings.JIRA_ISSUE_DEFAULTS
            settings.JIRA_REOPEN_CLOSED
            settings.JIRA_WONT_FIX

            auth = getattr(settings, "JIRA_AUTH_TYPE", "basic").lower()
            if auth not in ("basic", "oauth"):
                auth = "basic"

            # Set up JIRA Client
            if auth == "basic":
                self._jira = JIRA(
                    basic_auth=(settings.JIRA_USER, settings.JIRA_PASSWORD),
                    options={"server": settings.JIRA_URL})

        except AttributeError:
            raise MiddlewareNotUsed

    def process_exception(self, request, exc):
        try:
            # Don't log 404 errors
            if isinstance(exc, Http404):
                return

            exc_tb = traceback.extract_tb(sys.exc_info()[2])
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
                # This parses the traceback - so we can get the name of the
                # function which generated this exception
                caller = exc_tb[-1][2]

            # Build our issue title in the form
            # "ExceptionType thrown by function name"
            issue_title = re.sub(
                r'"', r'\\\"', type(exc).__name__ + ' thrown by ' + caller)
            issue_message = (
                repr(exc.message) + '\n\n' +
                '{noformat:title=Traceback}\n' + traceback.format_exc() + '\n{noformat}\n\n' +
                '{noformat:title=Request}\n' + repr(request) + '\n{noformat}')

            # See if this exception has already been reported inside JIRA
            try:
                existing = self._jira.search_issues(
                    'project = "' + settings.JIRA_ISSUE_DEFAULTS['project']["key"] +
                    '" AND summary ~ "' + issue_title + '"',
                    maxResults=1)
            except JIRAError:
                raise

            # If it has, add a comment noting that we've had another report of it
            found = False
            for issue in existing:
                if issue_title == issue.fields.summary:

                    # If this issue is closed, reopen it
                    if int(issue.fields.status.id) in settings.JIRA_REOPEN_CLOSED \
                            and (issue.fields.resolution and int(issue.fields.resolution.id) != settings.JIRA_WONT_FIX):
                        self._jira.transition_issue(
                            issue, str(settings.JIRA_REOPEN_ACTION))

                        reopened = True
                    else:
                        reopened = False

                    # Add a comment
                    if reopened or not getattr(settings, 'JIRA_COMMENT_REOPEN_ONLY', False):
                        self._jira.add_comment(issue, issue_message)

                    found = True
                    break

            if not found:
                # Otherwise, create it
                issue = settings.JIRA_ISSUE_DEFAULTS.copy()
                issue['summary'] = issue_title
                issue['description'] = issue_message

                self._jira.create_issue(fields=issue)
        except:
            raise
        else:
            settings.ADMINS = ()
