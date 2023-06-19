try:
    import unzip_requirements # type: ignore
except ImportError:
    pass

import json
import logging
import os
import re
import textwrap

from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

from connector import datadog_connector, github_connector

_logger = logging.getLogger(__name__)

MESSAGE_CHUNK_SIZE = 2500


def _return_first_response(client, channel_id, message_ts):
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Searching...",
            }
        }
    ]
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=message_ts,
        blocks=blocks,
    )


def _parse_shortcut_data(shortcut):
    message_ts = shortcut["message_ts"]
    channel_id = shortcut["channel"]["id"]
    from_ts = None
    to_ts = None
    for attachment in shortcut["message"]["attachments"]:
        if "View in Log Explorer" in attachment["title"]:
            link = attachment["title_link"]

            # extract "from_ts" and "to_ts" from query string in link
            m = re.match(".*from_ts=(\d+)&to_ts=(\d+).*", link)
            from_ts = m.group(1) if m else None
            to_ts = m.group(2) if m else None
            break
    return {
        "message_ts": message_ts,
        "channel_id": channel_id,
        "from_ts": from_ts,
        "to_ts": to_ts,
    }


def _get_similar_issues(stacktrace):
    res = github_connector.run_query(stacktrace)
    if res is not None:
        created_at = res.created_at.strftime("%Y-%m-%d %H:%M:%S")
        label_str = ", ".join(res.labels)
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Found similar issue"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*URL:*\n<{res.url}|{res.title}>"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*State:*\n{res.state}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Created at:*\n{created_at}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Labels:*\n{label_str}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Comment:*\n{int(res.comments)}"
                    }
                ]
            }
        ]
    else:
        issue_url = os.environ["NEW_ISSUE_URL"]
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"No similar issue found"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Please create new issue: *<{issue_url}|here>*"
                }
            }
        ]
    return blocks


def open_modal(shortcut, client):
    try:
        _logger.info(f"Slack shortcut event: {json.dumps(shortcut)}")
        d = _parse_shortcut_data(shortcut)
        # stacktraces = _query_logs(d["from_ts"], d["to_ts"])
        channel_id = d["channel_id"]
        message_ts = d["message_ts"]
        _return_first_response(client, channel_id, message_ts)

        # for i, s in enumerate(stacktraces):
        #     # _logger.info(f"stacktrace {i}: {s}")
        #     if s:

        stacktrace = datadog_connector.query_logs(d["from_ts"], d["to_ts"])
        _logger.info(f"stacktrace: {stacktrace}")
        
        chunks = textwrap.wrap(stacktrace, MESSAGE_CHUNK_SIZE)
        for chunk in chunks:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=message_ts,
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"```{chunk}```"},
                    },
                ],
            )
        
        # LLMsによるquery
        blocks = _get_similar_issues(stacktrace)
        client.chat_postMessage(
            channel=d["channel_id"],
            thread_ts=d["message_ts"],
            blocks=blocks
        )
    except Exception as e:
        _logger.exception(e)
        raise


app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    token=os.environ.get("SLACK_BOT_TOKEN"),
    process_before_response=True,  # necessary for AWS Lambda
)


app.shortcut("defense")(
    ack=lambda ack: ack(),
    lazy=[open_modal],
)


def handler(event, context):
    _logger.info(event)
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)
