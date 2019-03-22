#!/usr/bin/env python3

from stacker.context import Context
from stacker.actions import build
from stacker.providers.aws.default import Provider
import fabric

"""
e2e test with real EC2 instances

  1. Packer bake with local ebspin
  2. Create 1:1:1 ASG with 1 AZ. Userdata places randomly named file on mount
  3. SSH to instance and md5sum/count files
  4. Terminate, SSH and assert count +1
  5. Change AZ (updatepolicy forces update), assert count +1
  6. Change to 3rd AZ, assert count +1
  7. Scale down to 0, delete volumes, scale up, assert count +1
  8. Finally, delete CFN and volumes/snapshots
"""

env = {"namespace": "namespace-here"}
config = {
    "stacks": [
        {
            "name": "ebspin-test",
            "template-path": "./ebspin_cloudformation.yml",
            "variables": {
                "az": "ap-southeast-2a"
            }
        }
    ]
}
context = Context(environment=env, config=config)

action = build.Action(context, provider=Provider("us-east-1"))
action.run()

client = boto3.client('autoscaling')
client.describe_auto_scaling_groups(
    AutoScalingGroupNames=[
        'string',
    ])

fabric.Connection(
