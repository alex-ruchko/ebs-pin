#!/usr/bin/env python3

import json
import logging
import backoff
import botocore
import boto3
from stacker.context import Context
from stacker.config import Config, parse
from stacker.actions import build
from stacker.actions import destroy
from stacker.session_cache import get_session
from stacker.providers.aws.default import ProviderBuilder
from stacker.commands.stacker.build import Build
from stacker.logger import setup_logging
import fabric
import pdb

setup_logging(verbosity=0)

logger = logging.getLogger(__name__)


"""
e2e test with real EC2 instances

  1. Packer bake with local ebs-pin
  2. Create 1:1:1 ASG with 1 AZ. Userdata places randomly named file on mount
  3. SSH to instance and md5sum/count files
  4. Terminate, SSH and assert count +1
  5. Change AZ (updatepolicy forces update), assert count +1
  6. Change to 3rd AZ, assert count +1
  7. Scale down to 0, delete volumes, scale up, assert count +1
  8. Finally, delete CFN and volumes/snapshots
"""

@backoff.on_predicate(backoff.expo, max_time=600)
@backoff.on_exception(backoff.expo, TimeoutError, max_time=600)
def get_hostnames_file(instance_ip):
    hostnames = None
    result = fabric.Connection(user='ec2-user', host=instance_ip).run('cat /media/ebs-pin/hostnames', hide=True)
    hostnames = result.stdout.strip()
    logging.info("/media/ebs-pin/hostnames: {}".format(hostnames))
    return hostnames


@backoff.on_exception(backoff.expo, TimeoutError, max_time=600)
def wait_for_connection(instance_ip):
    fabric.Connection(user='ec2-user', host=instance_ip)


@backoff.on_predicate(backoff.expo)
@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def tail_console_logs(instance_id, ec2, stop_on="reboot: Power down", previous_output=None):
    response = ec2.get_console_output(InstanceId=instance_id)
    logging.debug(response)
    if response.get('Output', None) == None:
        return False

    if previous_output == None:
        print(response['Output'])
        if stop_on in response['Output']:
            logging.info('Finished tailing console output.')
            return True
    elif len(response['Output']) > len(previous_output):
        print(response['Output'].replace(previous_output, ''))  # only print the delta
        if stop_on in response['Output']:
            logging.info('Finished tailing console output.')
            return True
        else:
            tail_console_logs(stop_on=stop_on, instance_id=instance_id, client=client, previous_output=response['Output'])
            return True
    else:
        state = ec2.describe_instances(
            InstanceIds=[instance_id]
        )['Reservations'][0]['Instances'][0]['State']['Name']
        if state != "running":
            return True
        else:
            return False



@backoff.on_exception(backoff.expo, IndexError)
def get_instance_in_subnet_from_asg(asg_name, subnet_id, autoscaling=boto3.client('autoscaling'), ec2=boto3.client('ec2')):
    instance_id = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )['AutoScalingGroups'][0]['Instances'][0]['InstanceId']

    try:
        old_instance = ec2.describe_instances(
            Filters=[
                {
                    'Name': 'instance-state-name',
                    'Values': [
                        'running'
                    ]
                }
            ],
            InstanceIds=[instance_id]
        )['Reservations'][0]['Instances'][0]
        if old_instance['SubnetId'] != subnet_id:
            logging.info('Terminating old instance {} in wrong subnet ({}, expected {})...'.format(old_instance['InstanceId'], old_instance['SubnetId'], subnet_id))
            ec2.terminate_instances(InstanceIds=[old_instance['InstanceId']])
            waiter = ec2.get_waiter('instance_terminated')
            waiter.wait(InstanceIds=[old_instance['InstanceId']])
    except (IndexError):
        pass

    instance = ec2.describe_instances(
        Filters=[
            {
                'Name': 'subnet-id',
                'Values': [
                    subnet_id
                ]
            }
        ],
        InstanceIds=[instance_id]
    )['Reservations'][0]['Instances'][0]

    logging.info("instance_id: {}".format(instance['InstanceId']))
    logging.info("instance subnet_id: {}".format(instance['SubnetId']))
    return instance


def return_count_after_update(asg_name, subnet_id, autoscaling=boto3.client('autoscaling'), ec2=boto3.client("ec2")):
    instance = get_instance_in_subnet_from_asg(asg_name, subnet_id, autoscaling, ec2)
    instance_id = instance['InstanceId']

    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])

    instance_ip = instance['PublicIpAddress']
    logging.info("instance_ip: {}".format(instance_ip))

    wait_for_connection(instance_ip)

    tail_console_logs(stop_on="finished at", instance_id=instance_id, ec2=ec2)

    hostnames = get_hostnames_file(instance_ip)
    count = len(hostnames.splitlines())
    return count


def construct_context(subnet_id):
    config_dict = {
        "namespace": "",
        "namespace_delimiter": "",
        "stacker_bucket": "",
        "bucket_region": "ap-southeast-2",
        "region": "ap-southeast-2",
        "stacks": [
            {
                "name": "ebs-pin-test",
                "template_path": "./cloudformation.yml",
                "variables": {
                    "AvailabilityZone": "ap-southeast-2a",
                    "AMI": ami,
                    "VpcId": vpc_id,
                    "Subnets": subnet_id,
                    "KeyName": "id_rsa"
                },
                "tags": {
                    "Name": "ebs-pin-test"
                }
            }
        ]
    }
    config = Config(config_dict)
    context = Context(config=config)
    return context

try:
    context = None

    builds = json.loads(open("manifest.json", 'r').read())['builds']
    
    ami = sorted(builds, key=lambda x: x['build_time'], reverse=True)[0]['artifact_id'].split(':')[1]
    logging.info("AMI: {}".format(ami))

    ec2 = boto3.client('ec2')
    vpc_id = ec2.describe_vpcs(
        Filters=[
            {
                'Name': 'isDefault',
                'Values': [
                    'true'
                ]
            }
        ]
    )['Vpcs'][0]['VpcId']

    response = ec2.describe_subnets(
        Filters=[
            {
                'Name': 'vpc-id',
                'Values': [
                    vpc_id
                ]
            }
        ]
    )
    subnet_ids = [x['SubnetId'] for x in response['Subnets']]

    provider_builder = ProviderBuilder(region="ap-southeast-2", recreate_failed=True, interactive=False)
    context = construct_context(subnet_ids[0])

    action = build.Action(context, provider_builder=provider_builder)
    action.run(tail=True)

    cloudformation = boto3.client("cloudformation")
    asg_name = cloudformation.describe_stack_resources(
        StackName="ebs-pin-test",
        LogicalResourceId="AutoScalingGroup"
    )['StackResources'][0]['PhysicalResourceId']
    logging.info("asg_name: {}".format(asg_name))

    autoscaling = boto3.client('autoscaling')
    count = return_count_after_update(asg_name, subnet_ids[0], autoscaling=autoscaling, ec2=ec2)
    assert count >= 1
    previous_count = count

    context = construct_context(subnet_ids[1])
    action = build.Action(context, provider_builder=provider_builder)
    action.run(tail=True)

    count = return_count_after_update(asg_name, subnet_ids[1], autoscaling=autoscaling, ec2=ec2)
    assert count >= previous_count + 1
    previous_count = count

    context = construct_context(subnet_ids[2])
    action = build.Action(context, provider_builder=provider_builder)
    action.run(tail=True)

    count = return_count_after_update(asg_name, subnet_ids[2], autoscaling=autoscaling, ec2=ec2)
    assert count >= previous_count + 1

    logging.info("Done!")
finally:
    if context:
        action = destroy.Action(context, provider_builder=provider_builder)
        action.run(tail=True, force=True)
