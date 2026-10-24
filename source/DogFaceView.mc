import Toybox.Activity;
import Toybox.ActivityMonitor;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;
import Toybox.WatchUi;

// Keeps the dog animation looping while the watch is awake.
class DogAnimationDelegate extends WatchUi.AnimationDelegate {

    private var _view as DogFaceView;

    function initialize(view as DogFaceView) {
        AnimationDelegate.initialize();
        _view = view;
    }

    function onAnimationEvent(event as AnimationEvent, options as Dictionary) as Void {
        if (event == WatchUi.ANIMATION_EVENT_COMPLETE) {
            _view.onLoopComplete();
        }
    }
}

// Watch face with an animated 3D puppy whose mood follows the day:
// sleepy overnight, happy once the step goal is met, awake otherwise.
// The animation loops while the screen is awake (the system stops it when
// the watch goes to sleep); in between, the first frame is drawn as a still
// so the face never looks empty.
class DogFaceView extends WatchUi.WatchFace {

    private const SLEEP_START_HOUR = 22;
    private const SLEEP_END_HOUR = 6;
    private const DOG_SIZE = 220;

    private var _mood as Symbol?;
    private var _dog as BitmapResource?;
    private var _animation as AnimationLayer?;
    private var _dogX as Number = 0;
    private var _dogY as Number = 0;
    private var _lowPower as Boolean = false;
    private var _burnInProtection as Boolean = false;

    function initialize() {
        WatchFace.initialize();
        var settings = System.getDeviceSettings();
        _burnInProtection = (settings has :requiresBurnInProtection) && settings.requiresBurnInProtection;
    }

    function onLayout(dc as Dc) as Void {
        _dogX = (dc.getWidth() - DOG_SIZE) / 2;
        _dogY = (dc.getHeight() * 0.34).toNumber();
        setMood(currentMood(System.getClockTime(), ActivityMonitor.getInfo()));
    }

    function onShow() as Void {
        startPlaying();
    }

    function onUpdate(dc as Dc) as Void {
        var width = dc.getWidth();
        var height = dc.getHeight();
        var clock = System.getClockTime();

        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();

        if (_lowPower && _burnInProtection) {
            drawAlwaysOn(dc, clock);
            return;
        }

        var activity = ActivityMonitor.getInfo();
        var mood = currentMood(clock, activity);
        if (mood != _mood) {
            setMood(mood);
        }

        drawBattery(dc, width / 2, (height * 0.075).toNumber());

        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(width / 2, height * 0.215, Graphics.FONT_NUMBER_HOT, formatTime(clock),
            Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);

        var dog = _dog;
        if (dog != null) {
            dc.drawBitmap(_dogX, _dogY, dog);
        }

        // Steps on the left, heart rate on the right, like the cat face
        var statY = (height * 0.53).toNumber();
        var leftX = (width * 0.13).toNumber();
        var rightX = (width * 0.87).toNumber();
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        drawSteps(dc, leftX, statY - 16);
        drawHeart(dc, rightX, statY - 18, 9);
        var steps = activity.steps != null ? activity.steps.toString() : "--";
        dc.drawText(leftX, statY, Graphics.FONT_XTINY, steps, Graphics.TEXT_JUSTIFY_CENTER);
        dc.drawText(rightX, statY, Graphics.FONT_XTINY, heartRate(), Graphics.TEXT_JUSTIFY_CENTER);

        var today = Gregorian.info(Time.now(), Time.FORMAT_MEDIUM);
        var date = Lang.format("$1$ $2$", [today.day_of_week.toUpper(), today.day]);
        dc.drawText(width / 2, height * 0.875, Graphics.FONT_TINY, date, Graphics.TEXT_JUSTIFY_CENTER);
    }

    function onEnterSleep() as Void {
        _lowPower = true;
        stopPlaying();
        WatchUi.requestUpdate();
    }

    function onExitSleep() as Void {
        _lowPower = false;
        startPlaying();
        WatchUi.requestUpdate();
    }

    function onLoopComplete() as Void {
        if (!_lowPower) {
            playLoop();
        }
    }

    private function startPlaying() as Void {
        if (_lowPower && _burnInProtection) {
            return;
        }
        playLoop();
    }

    private function playLoop() as Void {
        var animation = _animation;
        if (animation != null) {
            animation.setVisible(true);
            animation.play({:delegate => new DogAnimationDelegate(self)});
        }
    }

    // Hide the layer so the still frame underneath shows through.
    private function stopPlaying() as Void {
        var animation = _animation;
        if (animation != null) {
            animation.stop();
            animation.setVisible(false);
        }
    }

    // Swap in the still and the animation for a new mood, keeping only one
    // of each loaded.
    private function setMood(mood as Symbol) as Void {
        _mood = mood;
        var stillId = Rez.Drawables.DogAwake;
        var animationId = Rez.Drawables.DogAwakeAnimation;
        if (mood == :sleepy) {
            stillId = Rez.Drawables.DogSleepy;
            animationId = Rez.Drawables.DogSleepyAnimation;
        } else if (mood == :happy) {
            stillId = Rez.Drawables.DogHappy;
            animationId = Rez.Drawables.DogHappyAnimation;
        }
        _dog = null;
        _dog = WatchUi.loadResource(stillId) as BitmapResource;

        var old = _animation;
        if (old != null) {
            old.stop();
            removeLayer(old);
        }
        var animation = new WatchUi.AnimationLayer(animationId, null);
        animation.setLocation(_dogX, _dogY);
        animation.setVisible(false);
        addLayer(animation);
        _animation = animation;
    }

    // AMOLED always-on mode: only the time, dimmed, and nudged each minute
    // so the lit pixels stay under the burn-in limit and don't sit still.
    private function drawAlwaysOn(dc as Dc, clock as System.ClockTime) as Void {
        var offset = (clock.min % 5) * 4 - 8;
        dc.setColor(Graphics.COLOR_DK_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(dc.getWidth() / 2 + offset, dc.getHeight() / 2 + offset, Graphics.FONT_NUMBER_MEDIUM,
            formatTime(clock), Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
    }

    private function currentMood(clock as System.ClockTime, activity as ActivityMonitor.Info) as Symbol {
        if (clock.hour >= SLEEP_START_HOUR || clock.hour < SLEEP_END_HOUR) {
            return :sleepy;
        }
        var steps = activity.steps;
        var goal = activity.stepGoal;
        if (steps != null && goal != null && goal > 0 && steps >= goal) {
            return :happy;
        }
        return :awake;
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

    private function drawBattery(dc as Dc, x as Number, y as Number) as Void {
        var battery = System.getSystemStats().battery;
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
