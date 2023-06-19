# Desc: Selects the correct connector based on the config
from enum import Enum

from connector import datadog_connector, newrelic_connector, github_connector


class ErrorMonitoringConnector(Enum):
    DATADOG = 'datadog'
    NEWRELIC = 'newrelic'


def select_error_monitoring_connector(config):
    if config['errorMonitoringConnector'] == ErrorMonitoringConnector.DATADOG.value:
        return datadog_connector
    elif config['errorMonitoringConnector'] == ErrorMonitoringConnector.NEWRELIC.value:
        return newrelic_connector
    else:
        raise ValueError(f"Invalid errorMonitoringConnector: {config['errorMonitoringConnector']}")


def select_issue_tracker_connector(config):
    if config['issueTrackerConnector'] == 'github':
        return github_connector
    else:
        raise ValueError(f"Invalid issueTrackerConnector: {config['issueTrackerConnector']}")
