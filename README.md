trackdayvideo
==
Tools for processing video from multiple cameras, GPS logs and engine telemetry recorded at car track days.


Status
==
Very much a work in progress.


Usage
==
Place videos from multiple cameras into a structure like this:
```
sometrackday/front/GOPR0001.MP4
sometrackday/back/GOPR0021.MP4
sometrackday/inside/GOPR0031.MP4
```

Run ```assemble.py``` to analyse those videos, match them together and calculate sync offsets based on the GoPro HiLight tagging feature. Writes ```sessions.yaml```

Run ```preview.py 0``` to see all discovered videos for session 0 side-by-side, and synced together.

Run ```render.py 0``` to generate ```session-0.mlt```, which is the XML specification for the mlt video rendering tool.

Run ```melt xml:session-0.mlt -consumer avformat:session-0.mp4 acodec=aac vcodec=libx264``` to render the final video info session-0.mp4

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
* Call mlt from the render tool.
* Use mlt-provided property presets (https://www.mltframework.org/bin/view/MLT/PropertyPresets) to control output settings, and probably default to the ones recommended by YouTube. (https://forum.kde.org/viewtopic.php?f=272&t=124869#p329129 and https://support.google.com/youtube/answer/1722171?hl=en)


