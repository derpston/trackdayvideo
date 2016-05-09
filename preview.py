#!/usr/bin/env python
import yaml

import gtk
gtk.gdk.threads_init()

import sys
import vlc

from gettext import gettext as _

# Create a single vlc.Instance() to be shared by (possible) multiple players.
instance = vlc.Instance()

class VLCWidget(gtk.DrawingArea):
    """Simple VLC widget.

    Its player can be controlled through the 'player' attribute, which
    is a vlc.MediaPlayer() instance.
    """
    def __init__(self, *p):
        gtk.DrawingArea.__init__(self)
        self.player = instance.media_player_new()
        def handle_embed(*args):
            if sys.platform == 'win32':
                self.player.set_hwnd(self.window.handle)
            else:
                self.player.set_xwindow(self.window.xid)
            return True
        self.connect("map", handle_embed)
        self.set_size_request(320, 200)

class DecoratedVLCWidget(gtk.VBox):
    offset = None

    def __init__(self, videoplayers):
        gtk.VBox.__init__(self)
        self._vlc_widget = VLCWidget()
        self.videoplayers = videoplayers
        self.player = self._vlc_widget.player
        self.pack_start(self._vlc_widget, expand=True)
        self._toolbar = self.get_player_control_toolbar()
        self.pack_start(self._toolbar, expand=False)

    def get_player_control_toolbar(self):
        """Return a player control toolbar
        """
        tb = gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)
        for text, tooltip, stock, callback in (
            (_("Play"), _("Play"), gtk.STOCK_MEDIA_PLAY, lambda b: self.player.play()),
            (_("Pause"), _("Pause"), gtk.STOCK_MEDIA_PAUSE, lambda b: self.player.pause()),
            (_("Stop"), _("Stop"), gtk.STOCK_MEDIA_STOP, lambda b: self.player.stop()),
            ):
            b=gtk.ToolButton(stock)
            b.set_tooltip_text(tooltip)
            b.connect("clicked", callback)
            tb.insert(b, -1)
        
        self.offset_widget = gtk.Label()
        
        labelcontainer = gtk.ToolItem()
        labelcontainer.add(self.offset_widget)
        tb.insert(labelcontainer, -1)

        #tb.insert(self.offset_widget, -1)
        tb.show_all()
        return tb
    
    def set_offset(self, offset):
        self.offset = offset
        if offset is None:
            offset_label = "Offset: fixed"
        else:
            offset_label = "Offset: %dms" % self.offset
            
            # Adjust this video's position to reflect the new offset.
            # This is calculated relative to the one 'fixed' video.
            fixed_video = [v for v in self.videoplayers.values() if v.offset in [None, 0]][0]
            ts = fixed_video.player.get_time()
            this_ts = self.player.get_time()
            print ts, this_ts

        self.offset_widget.set_text(offset_label)

class VideoPlayer:
    """Example simple video player.
    """
    def __init__(self):
        self.vlc = DecoratedVLCWidget()

    def main(self, fname):
        self.vlc.player.set_media(instance.media_new(fname))
        w = gtk.Window()
        w.add(self.vlc)
        w.show_all()
        w.connect("destroy", gtk.main_quit)
        gtk.main()


class MultiVideoPlayer:
    videoplayers = {}
    def main(self, session):
        # Build main window
        window=gtk.Window()
        mainbox=gtk.VBox()
        videos=gtk.HBox()

        window.add(mainbox)
        mainbox.add(videos)
    
        paths = []
        for camera, view in session['views'].items():
            path = view['paths'][0]
            
            # Low res versions for speed. TODO make this configurable
            path = path.replace(".MP4", ".LRV")

            v = DecoratedVLCWidget(self.videoplayers)
            v.player.set_media(instance.media_new(path))
            v.player.set_rate(0.5)
            self.videoplayers[camera] = v
            videos.add(v)

        # Set the offsets after creating all the videos because the offsets
        # are computed relative to the fixed video.
        for camera, view in session['views'].items():
            self.videoplayers[camera].set_offset(view.get('offset', None))

        # Create global toolbar
        tb = gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        def execute(b, methodname):
            """Execute the given method on all VLC widgets.
            """
            for v in videos.get_children():
                getattr(v.player, methodname)()
            return True

        for text, tooltip, stock, callback, arg in (
            (_("Play"), _("Global play"), gtk.STOCK_MEDIA_PLAY, execute, "play"),
            (_("Pause"), _("Global pause"), gtk.STOCK_MEDIA_PAUSE, execute, "pause"),
            (_("Stop"), _("Global stop"), gtk.STOCK_MEDIA_STOP, execute, "stop"),
            ):
            b = gtk.ToolButton(stock)
            b.set_tooltip_text(tooltip)
            b.connect("clicked", callback, arg)
            tb.insert(b, -1)
        
        b = gtk.ToolButton()
        b.set_label("Load videos")
        b.connect("clicked", self.load_videos)
        tb.insert(b, 0)

        mainbox.pack_start(tb, expand=False)

        window.show_all()
        window.connect("destroy", gtk.main_quit)
        gtk.main()

    
    def load_videos(self, toolbutton):
        for camera, v in self.videoplayers.items():
            v.player.play()
            while not v.player.is_playing():
                pass
            v.player.pause()
            while v.player.is_playing():
                pass
            
            if v.offset is None:
                v.player.set_time(0)
            else:
                v.player.set_time(int(v.offset))

if __name__ == "__main__":
    sessions = yaml.load(open("sessions.yaml"))
    session = sessions[int(sys.argv[1])]
    import pprint
    pprint.pprint(session)
    mvp = MultiVideoPlayer()
    mvp.main(session)

