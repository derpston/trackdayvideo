#!/usr/bin/env python
import os
import sys
import argparse
import collections
import mlt
import hashlib
import yaml
import pprint
import jinja2

def get_video_details(path):
    profile = mlt.Profile("quarter_ntsc")
    producer = mlt.Producer(profile, path)

    details = {}

    if not producer.is_valid():
        return None

    if producer.get_length() < 1 or producer.get_length() == 0x7fffffff:
        return None

    if producer.get("seekable") == '0':
        print "File not seekable, this might not work."
    
    details['frames'] = producer.get_length()
    details['length'] = producer.get_length_time()
    details['fps'] = producer.get_fps()

    return details


parser = argparse.ArgumentParser()
parser.add_argument("--path", action="store", default="sessions.yaml")
parser.add_argument("--index", action="store", type=int, default=None, required=True)
parser.add_argument("--length", action="store", type=int, default=None)
parser.add_argument("--layout", action="store", default="front:inside:back")
args = parser.parse_args()

mlt.Factory.init()

try:
    session = yaml.load(open(args.path).read())[args.index]
except Exception, ex:
    print >> sys.stderr, "Failed to load session index %d from %s: %r" % (args.index, args.path, ex)
    raise SystemExit(1)
pprint.pprint(session)

layout = args.layout.split(":")

# Get number of frames in each video.
video_details = {}
for camera, view in session['views'].items():
    for path in view['paths']:
        video_details[path] = get_video_details(path)

    # Convert an offset in milliseconds to a number of frames. Use the
    # first video in a split series because the framerate won't change
    # during a series.
    try:
        view['offset_frames'] = int(round(view['offset'] / (1000 / 
            video_details.values()[0]['fps'])))
    except (KeyError, ZeroDivisionError) as ex:
        # No offset, or a zero offset.
        pass

# Filter videos and adjust the claimed length to match the command line args.
if args.length:
    for camera, view in session['views'].items():
        print camera
        frames = 0
        try:
            frames += view['offset_frames']
        except KeyError:
            pass
    
        for path in view['paths']:
            frames_left = args.length - frames
            print "This video provides %d frames, I have %d/%d left." % (video_details[path]['frames'], frames_left, args.length)
            video_details[path]['frames'] = min(video_details[path]['frames'], frames_left)
            frames += video_details[path]['frames']

# TODO detect from the video lengths?
last_frame = args.length

template = """<?xml version="1.0" ?>
<mlt>
{%- for camera, view in session.views.iteritems() %}
    <!-- {{ camera }} -->
    {%- for path in view.paths %}
    <producer id="{{camera}}:{{path}}">
        <property name="resource">{{path}}</property>
    </producer>
    {%- endfor %}
{% endfor %}

{%- for camera, view in session.views.iteritems() %}
    <playlist id="{{camera}}">
    {%- if view.offset %}
        <blank length="{{view.offset_frames}}" />
    {%- endif %}
    {%- for path in view.paths %}
        <entry producer="{{camera}}:{{path}}" in="0" out="{{video_details[path].frames}}"/>
    {%- endfor %}
    </playlist>
{% endfor %}

    <tractor id="tractor0">
        <multitrack>
        {%- for camera in layout %}
            {%- if session.views[camera] %}
            <track producer="{{camera}}" />
            {%- endif %}
        {%- endfor %}
        </multitrack>
    
        {%- if session.views|length > 1 %}
        <transition in="0" out="{{last_frame}}">
            <property name="mlt_service">composite</property>
            <property name="a_track">0</property>
            <property name="b_track">1</property>
            <property name="progressive">1</property>
            <property name="geometry">0=70%,70%:30%x30%:70; -1=70%,70%:30%x30%:70; </property>
            <property name="halign">centre</property>
            <property name="valign">centre</property>
            <property name="distort">0</property>
            <property name="fill">1</property>
        </transition>
        <transition in="0" out="{{last_frame}}">
            <property name="mlt_service">mix</property>
            <property name="a_track">0</property>
            <property name="b_track">1</property>
            <property name="combine">1</property>
            <property name="always_active">1</property>
        </transition>
        {%- endif %}

        {%- if session.views|length > 2 %}
        <transition in="0" out="{{last_frame}}">
            <property name="mlt_service">composite</property>
            <property name="a_track">0</property>
            <property name="b_track">2</property>
            <property name="progressive">1</property>
            <property name="geometry">0=0%,70%:30%x30%:70; -1=0%,70%:30%x30%:70; </property>
            <property name="halign">centre</property>
            <property name="valign">centre</property>
            <property name="distort">0</property>
            <property name="fill">1</property>
        </transition>
        <transition in="0" out="{{last_frame}}">
            <property name="mlt_service">mix</property>
            <property name="a_track">0</property>
            <property name="b_track">2</property>
            <property name="combine">1</property>
            <property name="always_active">1</property>
        </transition>
        {%- endif %}

    </tractor>
</mlt>
"""

tmpl = jinja2.Template(template)
xml = tmpl.render(session=session
    ,   video_details=video_details
    ,   last_frame=last_frame
    ,   layout=layout
    )

open("session-%d.mlt" % args.index, "w").write(xml)

