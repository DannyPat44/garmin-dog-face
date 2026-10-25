import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

class DogFaceApp extends Application.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state as Dictionary?) as Void {
    }

    function onStop(state as Dictionary?) as Void {
    }

    function getInitialView() as [Views] or [Views, InputDelegates] {
        return [new DogFaceView()];
    }

    // Which dogs take turns; the face catches up when it's shown again
    function getSettingsView() as [Views] or [Views, InputDelegates] or Null {
        return [new DogSettingsMenu(), new DogSettingsDelegate()];
    }
}

function getApp() as DogFaceApp {
    return Application.getApp() as DogFaceApp;
}
