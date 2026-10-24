import Toybox.Activity;
import Toybox.ActivityMonitor;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;
import Toybox.WatchUi;

// Watch face with a cartoon dog whose mood follows the day:
// sleepy overnight, happy once the step goal is met, awake otherwise.
class DogFaceView extends WatchUi.WatchFace {

    private const SLEEP_START_HOUR = 22;
    private const SLEEP_END_HOUR = 6;

    private var _dog as BitmapResource?;
    private var _mood as Symbol?;
    private var _lowPower as Boolean = false;
    private var _burnInProtection as Boolean = false;

    function initialize() {
        WatchFace.initialize();
        var settings = System.getDeviceSettings();
        _burnInProtection = (settings has :requiresBurnInProtection) && settings.requiresBurnInProtection;
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

        // Date
        var today = Gregorian.info(Time.now(), Time.FORMAT_MEDIUM);
        var date = Lang.format("$1$ $2$ $3$", [today.day_of_week, today.month, today.day]);
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(width / 2, height * 0.10, Graphics.FONT_XTINY, date, Graphics.TEXT_JUSTIFY_CENTER);

        // Time
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(width / 2, height * 0.27, Graphics.FONT_NUMBER_MEDIUM, formatTime(clock),
            Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);

        // Dog
        var dog = dogFor(moodFor(clock, activity));
        dc.drawBitmap(width / 2 - dog.getWidth() / 2, height * 0.63 - dog.getHeight() / 2, dog);

        // Heart rate, steps and battery along the bottom
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(width / 2, height * 0.86, Graphics.FONT_XTINY, formatStats(activity),
            Graphics.TEXT_JUSTIFY_CENTER);
    }

    function onEnterSleep() as Void {
        _lowPower = true;
        WatchUi.requestUpdate();
    }

    function onExitSleep() as Void {
        _lowPower = false;
        WatchUi.requestUpdate();
    }

    // AMOLED always-on mode: only the time, dimmed, and nudged each minute
    // so the lit pixels stay under the burn-in limit and don't sit still.
    private function drawAlwaysOn(dc as Dc, clock as System.ClockTime) as Void {
        var offset = (clock.min % 5) * 4 - 8;
        dc.setColor(Graphics.COLOR_DK_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(dc.getWidth() / 2 + offset, dc.getHeight() / 2 + offset, Graphics.FONT_NUMBER_MEDIUM,
            formatTime(clock), Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
    }

    private function moodFor(clock as System.ClockTime, activity as ActivityMonitor.Info) as Symbol {
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

    // Keep only the current mood's bitmap loaded to save memory.
    private function dogFor(mood as Symbol) as BitmapResource {
        if (_dog == null || mood != _mood) {
            _dog = null;
            var id = Rez.Drawables.DogAwake;
            if (mood == :sleepy) {
                id = Rez.Drawables.DogSleepy;
            } else if (mood == :happy) {
                id = Rez.Drawables.DogHappy;
            }
            _dog = WatchUi.loadResource(id) as BitmapResource;
            _mood = mood;
        }
        return _dog as BitmapResource;
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

    private function formatStats(activity as ActivityMonitor.Info) as String {
        var heartRate = "--";
        var info = Activity.getActivityInfo();
        if (info != null && info.currentHeartRate != null) {
            heartRate = info.currentHeartRate.toString();
        }
        var steps = activity.steps != null ? activity.steps.toString() : "--";
        var battery = System.getSystemStats().battery.format("%d");
        return Lang.format("$1$ bpm   $2$   $3$%", [heartRate, steps, battery]);
    }
}
