import sys
import logging
import warnings

from django.conf import settings
from django.http import Http404
from django.core.exceptions import MiddlewareNotUsed

from django_jira import log


class JiraMiddlewareHandler(log.JiraHandler):
    """
    Leave firing emails as a fallback to Django itself.
    """

    def emit(self, record):
        """
        Leave firing emails as a fallback to Django itself.
        """
        self._emit(record)


class JiraExceptionReporterMiddleware:

    def __init__(self):
        warnings.warn(
            '{0} is deprecated, use {1}.{2} in the logging config instead'
            .format(
                self.__class__,
                log.JiraHandler.__module__, log.JiraHandler.__name__),
            DeprecationWarning)

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
            self.handler = JiraMiddlewareHandler(
                server_url=settings.JIRA_URL,
                user=settings.JIRA_USER, password=settings.JIRA_PASSWORD,
                auth_type=getattr(settings, "JIRA_AUTH_TYPE", "basic").lower(),
                issue_defaults=settings.JIRA_ISSUE_DEFAULTS,
                reopen_closed=settings.JIRA_REOPEN_CLOSED,
                reopen_action=settings.JIRA_REOPEN_ACTION,
                wont_fix=settings.JIRA_WONT_FIX,
                comment_reopen_only=getattr(
                    settings, 'JIRA_COMMENT_REOPEN_ONLY', False))

            if self.handler.unused:
                raise MiddlewareNotUsed

            # Set up JIRA Client
            self.handler._jira

            self.logger = (
                # Mimic the Django exception logger
                # From logging.Manager.getLogger
                logging.Logger.manager.loggerClass or logging._loggerClass
            )(
                # From django.core.handlers.base:logger
                'django.request')
            self.logger.addHandler(self.handler)

        except AttributeError:
            raise MiddlewareNotUsed

    def process_exception(self, request, exc):
        try:
            # Don't log 404 errors
            if isinstance(exc, Http404):
                return

            # From
            # django.core.handlers.base:BaseHandler.handle_uncaught_exception
            self.logger.error(
                'Internal Server Error: %s', request.path,
                exc_info=sys.exc_info(),
                extra={
                    'status_code': 500,
                    'request': request})
        except:
            raise
        else:
            settings.ADMINS = ()
