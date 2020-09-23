"""streaming server"""
from __future__ import (absolute_import, division, print_function, unicode_literals)
import sys
sys.path.append(".")
import os
import time
import json
from flask import Flask, render_template, Response, request, jsonify, send_file, stream_with_context, g
from sqlalchemy import create_engine
from werkzeug.utils import secure_filename
import psutil
import GPUtil
from sendgrid import SendGridAPIClient
# from sqlalchemy.ext.declarative import declarative_base
import subprocess as sp
from distutils.dir_util import copy_tree
from sqlalchemy.exc import ProgrammingError, OperationalError, SQLAlchemyError
from sqlalchemy_utils import database_exists, create_database
import base64
import re
import traceback
from datetime import datetime
import gzip
from io import BytesIO as IO
import redis
import jwt
from datetime import datetime
import uuid
import bcrypt
from itsdangerous import URLSafeSerializer
import random
import string
import requests
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, create_engine, ForeignKey, Table, JSON
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.types import BLOB, Integer, Interval, String, DateTime, BIGINT, Text
from sqlalchemy_utils import ChoiceType, URLType
from sqlalchemy.orm import relationship


APP = Flask(__name__)

Base = declarative_base()

DB_NAME = "trueface"


DB_URL = "mysql://root:truefacedb@127.0.0.1"
DB_PORT = 3306


class Video(Base):
    """represents a stream"""
    __tablename__ = 'video'
    id = Column(BIGINT, primary_key=True)
    source = Column(String(length=180))
    length = Column(Integer)

class VideoPart(Base):
    """represents a video part belonging to a stream"""
    STAGES = [
        ('fr', 'fr'),
        ('object', 'object'),
        ('threat', 'threat'),
        ('encode', 'encode')
    ]
    __tablename__ = 'edgevideopart'
    id = Column(BIGINT, primary_key=True)
    stage = Column(ChoiceType(STAGES))
    stages_count = Column(Integer, default=0)
    source = Column(String(length=180))
    timestamp = Column(BIGINT)
    video = relationship(
        'Video', foreign_keys=[id], primaryjoin='Video.id == VideoPart.id')
    video_path = Column(String(length=180))
    encoded_video_path = Column(String(length=180))
    length = Column(BIGINT)

def create_db_engine():
    """creates engine and db if it doesn't exist"""
    db = create_engine(
        '{}:{}/{}'.format(DB_URL, DB_PORT, DB_NAME),
        pool_recycle=300,
        max_overflow=500,
        pool_size=200,
        pool_pre_ping=True, connect_args={'connect_timeout': 3600})
    if not database_exists(db.url):
        create_database(db.url)

    db.execute('USE {};'.format(DB_NAME))
    Base.metadata.create_all(db)
    return db

@APP.route("/video/<video>")
def serve_video(video):
    """serve video
    TEST DONE
    """
    DB = create_db_engine()
    results = DB.execute(
                'SELECT video_path FROM {}.edgevideopart WHERE edgevideopart.id = {}'.format(DB_NAME, video))

    video = [result for result in results]
    video = video[0][0]

    video = open(video, 'rb').read()
    return video

@APP.route("/variant/<stream>.m3u8")
def variant(stream):
    """
    TEST DONE
    """
    manifest = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=3000000
/playlist/{}.m3u8
    """.format(stream)

    gzip_buffer = IO()
    gzip_file = gzip.GzipFile(mode='wb',
                              fileobj=gzip_buffer)
    gzip_file.write(manifest.encode())
    gzip_file.close()

    return Response(gzip_buffer.getvalue(), mimetype="application/x-mpegURL", headers={
        "Content-Encoding":"gzip", 'Content-Length': len(gzip_buffer.getvalue())})

@APP.route("/playlist/<stream>.m3u8")
def playlist(stream):
    """
    """
    DB = create_db_engine()
    results = DB.execute(
                "SELECT * FROM {}.edgevideopart WHERE source='{}' AND video_path is NOT NULL order by timestamp desc limit 120".format(DB_NAME, stream))
    results = [result for result in results]
    start = time.time()
    segment_count = DB.execute("SELECT COUNT(*) FROM {}.edgevideopart WHERE source='{}' AND video_path is NOT NULL".format(DB_NAME, stream))
    segment_count = [segment for segment in segment_count][0][0]
    manifest =  \
"""#EXTM3U
#EXT-X-VERSION:7
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-TARGETDURATION:6
#EXT-X-PROGRAM-DATE-TIME:%s
#EXT-X-MEDIA-SEQUENCE:%s
""" % (
    datetime.utcfromtimestamp(results[-1].timestamp/1000).strftime('%Y-%m-%dT%H:%M:%S'), 
    segment_count)

    for result in results[::-1]:
        url = ("/video/{}".format(result.id))
        manifest += "\n#EXTINF:{}, \n{}\n#EXT-X-DISCONTINUITY ".format(float(result.length), url)

    gzip_buffer = IO()
    gzip_file = gzip.GzipFile(mode='wb',
                              fileobj=gzip_buffer)
    gzip_file.write(manifest.encode())
    gzip_file.close()
    return Response(gzip_buffer.getvalue(), mimetype="application/x-mpegURL", headers={
        "Content-Encoding":"gzip", 'Content-Length': len(gzip_buffer.getvalue())})

@APP.route("/crossdomain.xml")
def crossdomain():
    return Response(
        """<cross-domain-policy>
        <site-control permitted-cross-domain-policies="all"/>
        <allow-access-from domain="*" secure="true"/>
        <allow-http-request-headers-from domain="*" headers="*" secure="true"/>
        </cross-domain-policy>""", mimetype="text/xml")


@APP.route('/', defaults={'path': ''})
@APP.route('/<path:path>')
def home(path):
    page = 'index.html'
    return render_template(page)


if __name__ == '__main__':
    APP.run(host='0.0.0.0', port=8086, debug=True, threaded=True)
