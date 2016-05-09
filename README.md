trackdayvideo
==
Tools for processing video from multiple cameras, GPS logs and engine telemetry recorded at car track days.


Status
==
Very much a work in progress.


TODO
==
* Use argparse, damnit.
* Run in the context of one "track day" directory, discovering cameras, using the correct paths for files, etc.
* Discover a log file, and split it into segments.
* Support loading log files as segments and doing signature matching.
* Name sessions with the time they started and the duration, as well as the index from that day.
* Session ordering is janky and relies on one camera (hardcoded :() to be present for all sessions.
* The preview tool is really janky.
* The preview tool needs to allow adjustment of the offsets.
* The preview tool should allow doing a final render of the first N seconds for a proper preview.
* Specify dependencies like mp4file, mlt, yaml etc
* Split GoPro HMMT parsing out into a new library, stuff it into pip, etc.
* TESTS!
* CI
