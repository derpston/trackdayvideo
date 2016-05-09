#!/usr/bin/env python

import sys
import struct
import itertools
import glob
import os

import yaml
from mp4file.mp4file import Mp4File

def get_hmmt_data(parent):
    retval = None
    for atom in parent.get_atoms():
        if atom.name == "HMMT":

            # Read the HMMT payload from the open file, taking care to save
            # and reset the current offset of the file in case the Mp4File
            # object is making assumptions about its offset into the file.
            save_offset = parent.file.tell()
            parent.file.seek(atom.offset)
            hmmt_bytes = parent.file.read(atom.size)
            parent.file.seek(save_offset)
            
            # The offset seems to be imprecise, so we need to search for
            # the actual HMMT marker and take the data beyond that.
            hmmt_index = hmmt_bytes.find("HMMT")
            if hmmt_index != -1:
                return hmmt_bytes[hmmt_index + 4:]
    
        # The MP4 atom structure is a tree, recurse to visit all nodes.
        retval = get_hmmt_data(atom)

        if retval is not None:
            return retval

def get_tags(hmmt_data):
    if hmmt_data is None:
        return []

    # The first four bytes should represent a big endian unsigned int that
    # tell us how many tags are encoded in the rest of the HMMT payload.
    (num_tags,) = struct.unpack(">I", hmmt_data[:4])

    # Each tag is another big endian unsigned int representing the number of
    # milliseconds since recording began.
    # This unpacks each one and returns a list of these millisecond values.
    return list(struct.unpack(">" + ("I" * num_tags),
        hmmt_data[4:(4 * num_tags) + 4]))


def make_signature(tags):
    if len(tags) < 2:
        return []
        
    offset = tags[0]
    signature = [tag - offset for tag in tags[1:]]
    return signature

segments = []

class Segment(object):
    def __init__(self, path, camera):
        self.path = path
        self.camera = camera
        self.filename = os.path.basename(path)
        self.tags = get_tags(get_hmmt_data(Mp4File(path)))
        self.signature = make_signature(self.tags)
        self.forced_offsets = {}
        self.next_segment = None
        self.matched = set()
        self.prefix = self.filename[0:4]
        self.index = self.filename[4:8]

        if self.prefix == "GOPR":
            # Root segment.
            self.segment_index = 0
        else:
            self.segment_index = int(self.prefix[2:4])
    
    def __repr__(self):
        return "<Segment %s/%s>" % (self.camera, self.filename)

    def is_root_segment(self):
        return self.segment_index == 0

    def find_subsequent_segments(self, segments):
        """Attempt to match up any multi-part segments."""

        for other in segments:
            if other.camera != self.camera:
                # From another camera, not a related segment.
                continue

            if other.index != self.index:
                # Different index, not a related segment.
                continue
    
            if other.segment_index != self.segment_index + 1:
                # This is a related segment, but it is not the /next/ segment.
                continue
            
            self.next_segment = other
    
    def series(self):
        yield self

        # Follow the linked list starting at self.next_segment, yielding all
        # other segments found.
        nxt = self.next_segment
        while nxt is not None:
            yield nxt
            nxt = nxt.next_segment
    
    def get_score(self, other):
        if other == self:
            # Don't match against own segment.
            return None

        # If we have a forced offset, use that.
        try:
            return self.forced_offsets[other]
        except KeyError:
            pass
   
        if len(self.signature) != len(other.signature):
            # Signatures not the same length, they can't be a match.
            return None

        sigmatch = []
        for (a, b) in zip(self.signature, other.signature):
            sigmatch.append(abs(a - b))

        score = sum(sigmatch) / float(len(sigmatch))
        return score


    def find_other_camera_segments(self, segments):
        if len(self.signature) == 0:
            # No signature matching possible if we don't have a signature.
            return

        candidates = []

        for other in segments:
            score = self.get_score(other)
            if score is not None:
                candidates.append((other, score))
        
        if len(candidates) > 0:
            # The candidate with the lowest score is likely to be the
            # right one to match with this segment.
            candidates.sort(key=lambda (c, s): s)
            (segment, score) = candidates[0]

            # Set up a bidirectional mapping between these segments.
            self.matched.add(segment)
            segment.matched.add(self)

def add_view(session, segment, offset=None):
    try:
        session['views']
    except KeyError:
        session['views'] = {}
    
    view = {"paths": []}
    if offset is not None:
        view["offset"] = offset

    for seg in segment.series():
        view['paths'].append(seg.path)

    session['views'][segment.camera] = view

def get_segment_by_filename(segments, filename):
    for segment in segments:
        if segment.filename == filename:
            return segment
    raise KeyError("No segment with filename '%s'" % filename)

def get_all_matched_segments(segment, matched=None):
    if matched is None:
        matched = set()

    for seg in segment.matched:
        if seg not in matched:
            matched.add(seg)
            matched.update(get_all_matched_segments(seg, matched))
    
    return matched

if __name__ == '__main__':
    for camera_path in sys.argv[1:]:
        camera_name = os.path.basename(camera_path)
        for path in glob.glob(os.path.join(camera_path, "*.MP4")):
            segments.append(Segment(path, camera_name))
    
    # Once we've loaded all segments, ask each segment to try to find any
    # other segments that were recorded as part of the same session.
    for segment in segments:
        segment.find_subsequent_segments(segments)

    root_segments = [s for s in segments if s.is_root_segment()]
   
    # Attempt to have each root segment match itself with root segments from
    # other cameras, based on the timestamped tag metadata.
    for segment in root_segments:
        segment.find_other_camera_segments(root_segments) 
    
    # Apply corrections provided by the user.
    corrections = yaml.load(open("corrections.yaml").read())
    for correction in corrections:
        if correction['action'] == "forcematch":
            filename1, filename2 = correction['filenames'].split(" ")
            segment1 = get_segment_by_filename(segments, filename1)
            segment2 = get_segment_by_filename(segments, filename2)
            segment1.matched.add(segment2)
            segment2.matched.add(segment1)
            
            try:
                segment1.forced_offsets[segment2] = correction['offset']
                segment2.forced_offsets[segment1] = -correction['offset']
            except KeyError:
                # The user may not have provided an offset correction.
                pass

    for segment in root_segments:
        if len(segment.matched) == 0:
            print "%r doesn't have any synced matches" % segment

    sessions = []

    segments_used = set()

    for segment in root_segments:
        
        # Recursively find all the other segments this one has been matched with.
        all_matched_segments = get_all_matched_segments(segment)
        
        # Skip segments that don't have a signature, are matched with at least
        # one other segment, and that other segment does have a signature.
        # The reason for this is that all the offsets are calculated relative
        # to the *first* segment considered, and if that first segment doesn't
        # have a signature, no offsets can be calculated at all. This tries to
        # make sure that a segment with a signature will always be the first
        # segment in a session. At the same time, we shouldn't completely skip
        # sessions if none of the segments have signatures.
        if len(all_matched_segments) > 1 and \
            len(segment.signature) == 0 and \
            any(filter(lambda seg: len(seg.signature) > 0, all_matched_segments)):
            continue

        if segment not in segments_used:
            session = {}
            add_view(session, segment)
            segments_used.add(segment)

            for other in all_matched_segments:
                score = segment.get_score(other)
                if score is None:
                    # If there's no match score between these two segments,
                    # we have no way of calculating an offset. Assume no
                    # offset and hope they line up well, or perhaps the user
                    # will provide an offset manually later.
                    score = 0

                # Convert the score to an offset with a direction.
                try:
                    if segment.tags[0] > other.tags[0]:
                        offset = -score
                    else:
                        offset = score
                except IndexError:
                    offset = None

                add_view(session, other, offset)
                segments_used.add(other)

            # When all the views have been loaded, look at all the offsets
            # and align them all to the smallest one so that there are no
            # negative offsets in the output. This is desirable because
            # whatever video processing tools operate on this later will
            # laugh at the concept of seeking to a negative offset.

            views_by_offset = []
            for camera, view in session['views'].items():
                views_by_offset.append([camera, view.get('offset', 0)])

            views_by_offset.sort(key=lambda (cam, off): off)
            for view in views_by_offset:
                if view[1] < 0:
                    adj = -view[1]
                    # Add adj to every offset.
                    for view in views_by_offset:
                        view[1] += adj
            for camera, offset in views_by_offset:
                session['views'][camera]['offset'] = offset

            sessions.append(session)

    # Sort sessions by filename order
    sessions.sort(key=lambda s: s['views']['front']['paths'][0])
   
    # Write all the session data out to a file.
    open("sessions.yaml", "w").write(yaml.dump(sessions))
    
