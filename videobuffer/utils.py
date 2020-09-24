import json
import requests
import boto3_wasabi
import random
import string
import os

def get_random_string(length):
    #letters = string.ascii_lowercase
    letters = string.digits
    result_str = ''.join(random.choice(letters) for i in range(length))
    print("Random string of length", length, "is:", result_str)
    return result_str


class Wasabi():
    def __init__(self, access_key_id=None, secret_access_key=None):
        self.s3 = boto3_wasabi.client('s3',
          region_name='us-east-1',
          aws_access_key_id = os.environ["KEY_ID"],
          aws_secret_access_key = os.environ["SECRET_KEY"])
        

    
    def upload_file(self, file, bucket_name, upload_name):
        self.s3.upload_file(file, bucket_name, upload_name)

    def upload_file_string(self, file, bucket_name, upload_name, ContentType="image/jpeg"):
        object = self.s3.Object(bucket_name, upload_name)
        object.put(Body=file, ContentType="image/jpeg")
        

    def set_bucket_policy(self, name):
        bucket_policy = {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Sid": "AllowPublicRead",
              "Effect": "Allow",
              "Principal": {
                "AWS": "*"
              },
              "Action": "s3:GetObject",
              "Resource": "arn:aws:s3:::{}/*".format(name)
            }
          ]
        }
        bucket_policy = json.dumps(bucket_policy)
        self.s3.put_bucket_policy(Bucket=name, Policy=bucket_policy)

    def bucket_exists(self, name):
        buckets = self.s3.list_buckets()
        buckets = [bucket['Name'] for bucket in buckets['Buckets']]
        if name not in buckets:
            return False
        return True