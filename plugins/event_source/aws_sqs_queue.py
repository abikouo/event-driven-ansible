"""
aws_sqs_queue.py

An ansible-rulebook event source plugin for receiving events via an AWS SQS queue.

Arguments:
    access_key:    Optional AWS access key ID
    secret_key:    Optional AWS secret access key
    session_token: Optional STS session token for use with temporary credentials
    endpoint_url:  Optional URL to connect to instead of the default AWS endpoints
    region:        Optional AWS region to use
    name:          Name of the queue
    delay_seconds: The SQS long polling duration. Set to 0 to disable. Defaults to 2.

Example:
    - ansible.eda.aws_sqs:
        region: us-east-1
        name: eda
        delay_seconds: 10
"""

import asyncio
import json
import logging
from typing import Any, Dict

import botocore.exceptions
from aiobotocore.session import get_session

from ..utils.aws_utils import connection_args


async def main(queue: asyncio.Queue, args: Dict[str, Any]):
    logger = logging.getLogger()

    if "name" not in args:
        raise ValueError("Missing queue name")
    queue_name = str(args.get("name"))
    wait_seconds = int(args.get("delay_seconds", 2))

    session = get_session()
    async with session.create_client("sqs", **connection_args(args)) as client:
        try:
            response = await client.get_queue_url(QueueName=queue_name)
        except botocore.exceptions.ClientError as err:
            if (
                err.response["Error"]["Code"]
                == "AWS.SimpleQueueService.NonExistentQueue"
            ):
                raise ValueError("Queue %s does not exist" % queue_name)
            else:
                raise

        queue_url = response["QueueUrl"]

        while True:
            # This loop wont spin really fast as there is
            # essentially a sleep in the receive_message call
            response = await client.receive_message(
                QueueUrl=queue_url,
                WaitTimeSeconds=wait_seconds,
            )

            if "Messages" in response:
                for msg in response["Messages"]:
                    meta = {"MessageId": msg["MessageId"]}
                    try:
                        msg_body = json.loads(msg["Body"])
                    except json.JSONDecodeError:
                        msg_body = msg["Body"]

                    await queue.put({"body": msg_body, "meta": meta})
                    await asyncio.sleep(0)

                    # Need to remove msg from queue or else it'll reappear
                    await client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=msg["ReceiptHandle"],
                    )
            else:
                logger.debug("No messages in queue")


if __name__ == "__main__":

    class MockQueue:
        async def put(self, event):
            print(event)

    asyncio.run(main(MockQueue(), {"region": "us-east-1", "name": "eda"}))
