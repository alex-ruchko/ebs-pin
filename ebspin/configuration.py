import requests, json, logging


class Configuration:
    def metadata(self):
        headers = {}
        try:
            r = requests.get(
                "http://169.254.169.254/latest/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                timeout=1,
            )
            token = r.text
            headers = {"X-aws-ec2-metadata-token": token}
            r.raise_for_status()
        except Exception:
            logger.warning(
                "Couldn't get IMDSv2 token, attempting to get instance ID without it..."
            )
            pass

        try:
            r = requests.get(
                "http://169.254.169.254/latest/dynamic/instance-identity/document",
                headers=headers,
                timeout=1,
            )
            r.raise_for_status()
            metadata = r.json()
            return metadata
        except json.decoder.JSONDecodeError as e:
            logging.error("Error decoding metadata: %s" % r.text)
            raise e
