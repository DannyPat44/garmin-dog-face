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
}

function getApp() as DogFaceApp {
    return Application.getApp() as DogFaceApp;
}
