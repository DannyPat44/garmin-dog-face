import Toybox.Application.Storage;
import Toybox.Lang;
import Toybox.WatchUi;

// The watch face's settings (hold Up, Watch Face, then Customize or the
// face's settings): a switch for each dog, kept on the watch. Every dog is on
// until switched off.

function isDogShown(name as String) as Boolean {
    var shown = Storage.getValue("show" + name);
    return shown == null || shown == true;
}

// The switches for every dog, in Dogs.mc's order
function shownDogs() as Array<Boolean> {
    var names = dogNames();
    var shown = [] as Array<Boolean>;
    for (var i = 0; i < names.size(); i++) {
        shown.add(isDogShown(names[i]));
    }
    return shown;
}

class DogSettingsMenu extends WatchUi.Menu2 {

    function initialize() {
        Menu2.initialize({:title => "Dogs"});
        var names = dogNames();
        for (var i = 0; i < names.size(); i++) {
            addItem(new WatchUi.ToggleMenuItem(names[i], null, names[i], isDogShown(names[i]), null));
        }
    }
}

class DogSettingsDelegate extends WatchUi.Menu2InputDelegate {

    function initialize() {
        Menu2InputDelegate.initialize();
    }

    function onSelect(item as MenuItem) as Void {
        if (item instanceof WatchUi.ToggleMenuItem) {
            Storage.setValue("show" + (item.getId() as String), item.isEnabled());
        }
    }
}
