"""stream capture script and queue producer"""
import time
import os
import argparse
import json
import logging
import cv2
from trueface.utils import RedisQueue
from trueface.fps import FPS
# from trueface.recognition import FaceRecognizer
from trueface.video import QVideoStream
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, create_engine, ForeignKey, Table, JSON
from sqlalchemy.types import BLOB, Integer, Interval, String, DateTime, BIGINT, Text
from sqlalchemy_utils import ChoiceType, URLType
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy_utils import database_exists, create_database


logging.basicConfig()


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


class CaptureService(object):
    """Stream Capture Class"""
    def __init__(self, args, config="./configuration/config.json"):
        self.args = args
        self.args['url'] = int(self.args['url']) if len(self.args['url']) == 1 else self.args['url']
        if args['fps']:
            self.fps = args['fps']
        else:
            self.fps = self.__measure_fps()
        self.cap = cv2.VideoCapture(args['url'])


    def __measure_fps(self, frames=100):
        #measure camera fps
        fps = FPS().start()
        cap = cv2.VideoCapture(self.args['url'])
        for frame in range(frames):
            cap.read()
            fps.update()

        fps.stop()
        fps = fps.fps()
        cap = None
        return fps

    def create_db_engine(self):
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
        return db


    def capture(self):
        """start stream capture"""

        #if storage volume doesn't exist create it
        if not os.path.isdir("./videos"):
            os.mkdir("./videos")

        width = int(self.cap.get(3))
        height = int(self.cap.get(4))
        stream_name = self.args['name']
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        #variable to keep track of segments recorded
        segement_count = 0

        #hash tracks if image freezes and returns the same, count keeps track of errors
        # last_frame_hash = None
        # last_frame_error_count = 0

        print("[INFO] approx. FPS: {:.2f}".format(self.fps))
        db = self.create_db_engine()
        session = sessionmaker(autoflush=False, autocommit=False)
        sess = session(bind=db)


        while True:
            start_time = time.time()
            filename = start_time
            print('start time', start_time)

            #init video writer
            out = cv2.VideoWriter(
                '%s/%s-%s.mp4' % ("./videos", stream_name, filename),
                fourcc, self.fps, (width, height))

            #reset frame count
            frame_count = 0

            #record desired segement
            while frame_count < (int(1)*self.fps):

                _, image = self.cap.read()

                if image is not None:
                    out.write(image)
                    frame_count += 1
                else:
                    print('broken image')
                    # last_frame_error_count += 1
                    break

            #release and destroy video recorder
            out.release()
            out = None

            #marks end of recording, not used at the moment
            end_timestamp = time.time()
            print('end time', end_timestamp)

            #keep count of segments recorded
            segement_count += 1

            #prepare queue data
            data = {
                "resolution":{
                    "width":width,
                    "height":height
                },
                "fps":self.fps,
                "timestamp":start_time,
                "video_name":'%s-%s.mp4' % (stream_name, filename),
                "video_path":'%s/%s-%s.mp4' % (
                    "./videos", stream_name, filename),
                "stream":stream_name,
                "start_time":start_time,
                "end_time":end_timestamp,
                "type":"capture",
                "frame_count":frame_count,
                "segment_duration":int(1)
            }


            video_part = VideoPart(
            source=stream_name,
            timestamp=start_time,
            video_path=data['video_path'],
            length=int(1))
            sess.add(video_part)
            sess.commit()

if __name__ == "__main__":
    ARGP = argparse.ArgumentParser(description="Trueface.ai Capture script")
    ARGP.add_argument("-u", "--url", default=0,
                      help="stream url to process")
    ARGP.add_argument("-n", "--name", default='test',
                      help="stream name, used for bucket and db as well")
    # ap.add_argument("-q", "--queue", default=False,
    #                 help="queue to push to")
    ARGP.add_argument("-d", "--duration", default=5,
                      help="segement duration")
    ARGP.add_argument("-t", "--threshold", default=0.5,
                      help="face detect threshold")
    ARGP.add_argument("-f", "--fps", default=None,
                      help="fps to use, it'll be measured if not set")

    #parse service arguments
    ARGS = vars(ARGP.parse_args())
    CaptureService(ARGS).capture()