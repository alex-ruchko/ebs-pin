#!/usr/bin/env python3
from ebspin import ec2
import boto3
from botocore.stub import Stubber, ANY
import botocore.exceptions
import unittest
from unittest.mock import Mock, patch
import logging
import datetime

class get_latest_volume_id_available_test(unittest.TestCase):

    def test_can_get_latest_volume_id(self):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        response = {"Volumes": [
            {"CreateTime": datetime.datetime.now(), "State": "available", "VolumeId": "old"},
            {"CreateTime": datetime.datetime.now() + datetime.timedelta(days=1), "State": "available", "VolumeId": "new"},
            {"CreateTime": datetime.datetime.now() + datetime.timedelta(days=2), "State": "in-use", "VolumeId": "newest"}
        ]}
        params = {'Filters': ANY}
        stubber.add_response('describe_volumes', response, )
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.get_latest_volume_id_available("foobar")
        self.assertEqual(response, "newest")

    def test_no_volumes_found(self):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        response = {"Volumes": []}
        params = {'Filters': ANY}
        stubber.add_response('describe_volumes', response, )
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.get_latest_volume_id_available("foobar")
        self.assertEqual(response, None)

    def test_raises_boto3_exception(self):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        stubber.add_client_error('describe_volumes', service_error_code="401")
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        with self.assertRaises(botocore.exceptions.ClientError):
            ebspin_ec2.get_latest_volume_id_available("foobar")


class get_latest_snapshot_idTest(unittest.TestCase):

    def test_can_get_latest_snapshot(self):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        response = {"Snapshots": [
            {"StartTime": datetime.datetime.now(), "State": "available", "SnapshotId": "old"},
            {"StartTime": datetime.datetime.now() + datetime.timedelta(days=1), "State": "available", "SnapshotId": "new"},
            {"StartTime": datetime.datetime.now() + datetime.timedelta(days=2), "State": "pending", "SnapshotId": "newest"}
        ]}
        params = {'Filters': ANY}
        stubber.add_response('describe_snapshots', response)
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.get_latest_snapshot_id("foobar")
        self.assertEqual(response, "newest")

    def test_no_snapshots_found(self):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        response = {"Snapshots": []}
        params = {'Filters': ANY}
        stubber.add_response('describe_snapshots', response)
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.get_latest_snapshot_id("foobar")
        self.assertEqual(response, None)

    def test_raises_boto3_exception(self):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        stubber.add_client_error('describe_snapshots', service_error_code="401")
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        with self.assertRaises(botocore.exceptions.ClientError):
            ebspin_ec2.get_latest_snapshot_id("foobar")


class attach_volume_test(unittest.TestCase):

    @patch('time.sleep')
    def test_can_wait_for_attach_volume(self, mock_sleep):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        stubber.add_response(  # return no results as volume is "in-use"
            'describe_volumes',
            {"Volumes": []}
        )
        stubber.add_response(
            'describe_volumes',
            {
                "Volumes": [
                    {"CreateTime": datetime.datetime.now() + datetime.timedelta(days=2), "State": "available", "VolumeId": "foo"}
                ]
            }
        )
        stubber.add_response(
                'attach_volume',
                {'AttachTime': datetime.datetime(2015, 1, 1)},
                {'VolumeId': ANY, 'InstanceId': ANY, 'Device': ANY}
        )
        stubber.add_response(  # return no results as volume is "available"
            'describe_volumes',
            {"Volumes": []}
        )
        stubber.add_response(
            'describe_volumes',
            {
                "Volumes": [
                    {
                        "State": "in-use",
                        "VolumeId": "foo",
                        "Attachments": [{"Device": "xvda", "InstanceId": "bar", "State": "attached"}]
                    }
                ]
            }
        )
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.attach_volume(volume_id="foo", instance_id="bar", device="xvda")
        self.assertEqual(response, "foo")


class create_snapshot_test(unittest.TestCase):

    @patch('time.sleep')
    def test_can_create_snapshot(self, mock_sleep):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        stubber.add_response('create_snapshot', {"SnapshotId": "foo"})
        stubber.add_response('describe_volumes', {"Volumes": [{"Tags": [{"Key": "Name", "Value": "bar-/dev/xvda"}, {"Key": "UUID", "Value": "01c6b711-a7d4-4bdf-bb2b-10b4b60594bc"}]}]})
        stubber.add_response('create_tags', {})
        stubber.add_response('describe_snapshots', {"Snapshots": []})
        stubber.add_response('describe_snapshots', {"Snapshots": [{"SnapshotId": "foo", "State": "completed"}]})
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.create_snapshot("foo", {"extra": "tag"})
        self.assertEqual(response, "foo")


class create_volume_test(unittest.TestCase):

    @patch('time.sleep')
    def test_can_create_volume(self, mock_sleep):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        stubber.add_response('create_volume', {"VolumeId": "foo"})
        stubber.add_response('describe_volumes', {"Volumes": [{"State": "in-use"}]})
        stubber.add_response('describe_volumes', {"Volumes": [{"State": "available"}]})
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.create_volume(10, "gp2", "ap-southeast-2a")
        self.assertEqual(response, "foo")

    @patch('time.sleep')
    def test_can_create_volume_from_snapshot(self, mock_sleep):
        client = boto3.client('ec2')
        stubber = Stubber(client)
        stubber.add_response('create_volume', {"VolumeId": "foo"})
        stubber.add_response('describe_volumes', {"Volumes": [{"State": "in-use"}]})
        stubber.add_response('describe_volumes', {"Volumes": [{"State": "available"}]})
        stubber.activate()
        ebspin_ec2 = ec2.Ec2(client)
        response = ebspin_ec2.create_volume(10, "gp2", "ap-southeast-2a", "foo")
        self.assertEqual(response, "foo")

if __name__ == "__main__":
    unittest.main(verbosity=2)
