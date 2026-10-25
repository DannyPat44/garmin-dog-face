import Toybox.Activity;
import Toybox.ActivityMonitor;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Math;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;
import Toybox.WatchUi;

// Moves on to the next clip when one finishes.
class DogAnimationDelegate extends WatchUi.AnimationDelegate {

    private var _view as DogFaceView;

    function initialize(view as DogFaceView) {
        AnimationDelegate.initialize();
        _view = view;
    }

    function onAnimationEvent(event as AnimationEvent, options as Dictionary) as Void {
        if (event == WatchUi.ANIMATION_EVENT_COMPLETE) {
            _view.onClipComplete();
        }
    }
}

// Watch face with animated 3D dogs (Millie, Nova and Ozzie; the list is
// generated into Dogs.mc) taking turns: each hour the dog on screen walks
// out and a different one, picked at random, walks in and sits (see Story).
// Her mood follows the day: happy once the step goal is met, awake
// otherwise, and at bedtime she lies down and sleeps the night.
// Clips play while the screen is awake (the system stops them when the
// watch goes to sleep, and the story skips to its end); under each clip is
// a still of its last frame, so the face never looks empty between clips or
// while asleep. The clock and stats are drawn on a layer above the
// animation, like the SDK's AnimationWatchFace sample, so the system never
// shows the dog layer on its own while the face redraws. Walks fill the
// whole screen, so the dogs come and go off its edge, under the stats.
class DogFaceView extends WatchUi.WatchFace {

    private const SLEEP_START_HOUR = 22;
    private const SLEEP_END_HOUR = 6;
    // Low enough that the date row and the clock's corners clear the round
    // edge of the screen; the clock overlaps the empty top of the dog's box
    private const ROW_TOP = 0.096;
    private const CLOCK_TOP = 0.145;

    private var _story as Story?;
    // [dog][mood] stills and [dog][clip] animations, in Story's order
    private var _stills as Array<Array<ResourceId> >;
    private var _clips as Array<Array<ResourceId> >;
    private var _still as BitmapResource?;
    private var _stillId as ResourceId?;
    private var _animation as AnimationLayer?;
    private var _face as Layer?;
    private var _dogX as Number = 0;
    private var _dogY as Number = 0;
    private var _clockFont as FontResource?;
    private var _clockY as Number = 0;
    private var _lowPower as Boolean = false;
    private var _playing as Boolean = false;
    private var _burnInProtection as Boolean = false;

    function initialize() {
        WatchFace.initialize();
        var settings = System.getDeviceSettings();
        _burnInProtection = (settings has :requiresBurnInProtection) && settings.requiresBurnInProtection;
        Math.srand(Time.now().value() + System.getTimer());
        _stills = dogStills();
        _clips = dogClips();
    }

    function onLayout(dc as Dc) as Void {
        var clockFont = WatchUi.loadResource(Rez.Fonts.ClockFont) as FontResource;
        _clockFont = clockFont;
        _clockY = (dc.getHeight() * CLOCK_TOP).toNumber();
        // The dog's box, where the clips are cropped to; the walks fill the
        // whole screen and are framed around it
        var box = DogLayout.box(dc.getWidth());
        _dogX = box[0];
        _dogY = box[1];
        var face = new WatchUi.Layer({:locX => 0, :locY => 0, :width => dc.getWidth(), :height => dc.getHeight()});
        addLayer(face);
        _face = face;
        var clock = System.getClockTime();
        _story = new Story(DogPicker.next(shownDogs(), null, Math.rand()), currentMood(clock, ActivityMonitor.getInfo()), clock.hour);
    }

    // Playback starts from onUpdate, once the face layer is current
    function onShow() as Void {
        updateStory();
        WatchUi.requestUpdate();
    }

    function onUpdate(dc as Dc) as Void {
        var clock = System.getClockTime();

        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();

        var face = _face;
        var faceDc = face != null ? face.getDc() : null;
        if (faceDc == null) {
            return;
        }
        faceDc.setColor(Graphics.COLOR_TRANSPARENT, Graphics.COLOR_TRANSPARENT);
        faceDc.clear();

        if (_lowPower && _burnInProtection) {
            // The face can be shown while already asleep (no onEnterSleep),
            // so make sure the dog is gone in always-on mode
            stopPlaying();
            drawAlwaysOn(faceDc, clock);
            return;
        }

        var activity = ActivityMonitor.getInfo();
        if (!_playing) {
            playNext();
        }
        var still = _still;
        if (still != null) {
            dc.drawBitmap(_dogX, _dogY, still);
        }
        drawFace(faceDc, clock, activity);
    }

    private function drawFace(dc as Dc, clock as System.ClockTime, activity as ActivityMonitor.Info) as Void {
        var width = dc.getWidth();
        var height = dc.getHeight();

        // Battery and date share the top row
        var today = Gregorian.info(Time.now(), Time.FORMAT_MEDIUM);
        var date = Lang.format("$1$ $2$", [today.day_of_week.toUpper(), today.day]);
        var rowY = (height * ROW_TOP).toNumber();
        var battery = System.getSystemStats().battery;
        var percent = battery.format("%d") + "%";
        var percentWidth = dc.getTextWidthInPixels(percent, Graphics.FONT_XTINY);
        var dateWidth = dc.getTextWidthInPixels(date, Graphics.FONT_XTINY);
        var rowLeft = width / 2 - (34 + percentWidth + 10 + dateWidth) / 2;
        drawBattery(dc, rowLeft + 14, rowY, battery);
        dc.setColor(battery < 20 ? Graphics.COLOR_RED : Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(rowLeft + 34, rowY, Graphics.FONT_XTINY, percent, Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(rowLeft + 34 + percentWidth + 10, rowY, Graphics.FONT_XTINY, date, Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);

        var clockFont = _clockFont;
        if (clockFont != null) {
            dc.drawText(width / 2, _clockY, clockFont, formatTime(clock), Graphics.TEXT_JUSTIFY_CENTER);
        }

        // Steps on the left, heart rate on the right, like the cat face;
        // outlined in black so they read over a dog walking past underneath
        var statY = (height * 0.53).toNumber();
        var leftX = (width * 0.13).toNumber();
        var rightX = (width * 0.87).toNumber();
        var steps = activity.steps != null ? activity.steps.toString() : "--";
        var heart = heartRate();
        var outline = [[-2, 0], [2, 0], [0, -2], [0, 2], [-1, -1], [1, 1], [-1, 1], [1, -1], [0, 0]];
        for (var i = 0; i < outline.size(); i++) {
            var dx = outline[i][0];
            var dy = outline[i][1];
            dc.setColor(dx == 0 && dy == 0 ? Graphics.COLOR_WHITE : Graphics.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
            drawSteps(dc, leftX + dx, statY - 16 + dy);
            drawHeart(dc, rightX + dx, statY - 18 + dy, 9);
            dc.drawText(leftX + dx, statY + dy, Graphics.FONT_XTINY, steps, Graphics.TEXT_JUSTIFY_CENTER);
            dc.drawText(rightX + dx, statY + dy, Graphics.FONT_XTINY, heart, Graphics.TEXT_JUSTIFY_CENTER);
        }
    }

    // The system stops animations when the view is hidden
    function onHide() as Void {
        stopPlaying();
    }

    // The screen went off: skip the rest of the story and show how it ends
    function onEnterSleep() as Void {
        _lowPower = true;
        stopPlaying();
        var story = _story;
        if (story != null) {
            story.skip();
            showStill(_stills[story.dog()][story.mood()]);
        }
        WatchUi.requestUpdate();
    }

    function onExitSleep() as Void {
        _lowPower = false;
        updateStory();
        WatchUi.requestUpdate();
    }

    function onClipComplete() as Void {
        if (_playing && !_lowPower) {
            playNext();
        }
    }

    // While the dog isn't moving on screen (waking up, or coming back to the
    // face), catch the story up with the time and her mood
    private function updateStory() as Void {
        var story = _story;
        if (story == null) {
            return;
        }
        var shown = shownDogs();
        var next = DogPicker.next(shown, story.dog(), Math.rand());
        if (!DogPicker.isAllowed(shown, story.dog())) {
            // She was switched off in the settings
            story.swapTo(next);
        }
        var clock = System.getClockTime();
        story.update(clock.hour, currentMood(clock, ActivityMonitor.getInfo()), next);
        if (story.isTelling()) {
            // Start the story now rather than finishing the current loop
            stopPlaying();
        }
    }

    // Play the story's next clip, with the still of its last frame underneath,
    // keeping only one animation and one still loaded
    private function playNext() as Void {
        var story = _story;
        if (story == null) {
            return;
        }
        var next = story.next();
        var clip = next[1];
        var mood = Story.endStill(clip);
        showStill(mood != null ? _stills[next[0]][mood] : null);

        var old = _animation;
        if (old != null) {
            old.stop();
            removeLayer(old);
            _animation = null;
        }
        var animation = new WatchUi.AnimationLayer(_clips[next[0]][clip], null);
        if (Story.fillsScreen(clip)) {
            animation.setLocation(0, 0);
        } else {
            animation.setLocation(_dogX, _dogY);
        }
        insertLayer(animation, 0);
        _animation = animation;
        _playing = true;
        animation.play({:delegate => new DogAnimationDelegate(self)});
    }

    private function showStill(id as ResourceId?) as Void {
        if (id == _stillId) {
            return;
        }
        _stillId = id;
        _still = null;
        if (id != null) {
            _still = WatchUi.loadResource(id) as BitmapResource;
        }
    }

    // Hide the layer so the still frame underneath shows through.
    private function stopPlaying() as Void {
        _playing = false;
        var animation = _animation;
        if (animation != null) {
            animation.stop();
            animation.setVisible(false);
        }
    }

    // AMOLED always-on mode: only the time, dimmed, and nudged each minute
    // so the lit pixels stay under the burn-in limit and don't sit still.
    private function drawAlwaysOn(dc as Dc, clock as System.ClockTime) as Void {
        var offset = (clock.min % 5) * 4 - 8;
        dc.setColor(Graphics.COLOR_DK_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(dc.getWidth() / 2 + offset, dc.getHeight() / 2 + offset, Graphics.FONT_NUMBER_MEDIUM,
            formatTime(clock), Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
    }

    private function currentMood(clock as System.ClockTime, activity as ActivityMonitor.Info) as Number {
        if (clock.hour >= SLEEP_START_HOUR || clock.hour < SLEEP_END_HOUR) {
            return Story.SLEEPY;
        }
        var steps = activity.steps;
        var goal = activity.stepGoal;
        if (steps != null && goal != null && goal > 0 && steps >= goal) {
            return Story.HAPPY;
        }
        return Story.AWAKE;
    }

    private function formatTime(clock as System.ClockTime) as String {
        var hour = clock.hour;
        if (!System.getDeviceSettings().is24Hour) {
            hour = hour % 12;
            if (hour == 0) {
                hour = 12;
            }
        }
        return Lang.format("$1$:$2$", [hour, clock.min.format("%02d")]);
    }

    private function heartRate() as String {
        var info = Activity.getActivityInfo();
        if (info != null && info.currentHeartRate != null) {
            return info.currentHeartRate.toString();
        }
        return "--";
    }

    private function drawBattery(dc as Dc, x as Number, y as Number, battery as Float) as Void {
        var w = 26;
        var h = 13;
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawRoundedRectangle(x - w / 2, y - h / 2, w, h, 3);
        dc.fillRectangle(x + w / 2, y - 3, 3, 6);
        dc.setPenWidth(1);
        dc.setColor(battery < 20 ? Graphics.COLOR_RED : Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.fillRectangle(x - w / 2 + 3, y - h / 2 + 3, ((w - 6) * battery / 100).toNumber(), h - 6);
    }

    private function drawHeart(dc as Dc, x as Number, y as Number, size as Number) as Void {
        var r = size / 2;
        dc.fillCircle(x - r, y, r);
        dc.fillCircle(x + r, y, r);
        dc.fillPolygon([[x - size, y + 1], [x + size, y + 1], [x, y + size + r]]);
    }

    private function drawSteps(dc as Dc, x as Number, y as Number) as Void {
        dc.fillEllipse(x - 5, y + 2, 4, 7);
        dc.fillEllipse(x + 5, y - 3, 4, 7);
        dc.fillCircle(x - 5, y + 12, 3);
        dc.fillCircle(x + 5, y + 7, 3);
    }
}
