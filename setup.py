from setuptools import setup

setup(
    name='ebs-pin3',
    version='0.3.4',
    scripts=['ebs-pin'],
    packages=['ebspin'],
    url='https://github.com/discobean/ebs-pin',
    description='Pin EBS volumes in a multi-az EC2 instance',
    install_requires=[
        'appdirs>=1.4.0',
        'boto3>=1.4.4',
        'botocore>=1.5.10',
        'docutils>=0.13.1',
        'futures>=3.0.5',
        'jmespath>=0.9.1',
        'packaging>=16.8',
        'pyparsing>=2.1.10',
        'python-dateutil>=2.6.0',
        'requests>=2.13.0',
        's3transfer>=0.1.10',
        'six>=1.10.0',
        'backoff>=1.8.0',
        'cryptography==2.4.2'
    ],
    keywords='ebs ebspin ebs-pin ebspin3'
)
