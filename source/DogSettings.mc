import Toybox.Application.Storage;
import Toybox.Lang;
import Toybox.WatchUi;

// The watch face's settings (hold Up, Watch Face, then Customize or the
// face's settings), kept on the watch: how often the dogs swap, and a switch
// for each dog. Every dog is on until switched off.

// How often the dogs swap, in minutes; 0 is every time you look
const SWAP_CHOICES = [0, 5, 15, 30, 60] as Array<Number>;
const SWAP_LABELS = ["Every look", "Every 5 min", "Every 15 min", "Every 30 min", "Every hour"] as Array<String>;
const SWAP_DEFAULT = 60;

function swapEvery() as Number {
    var every = Storage.getValue("swapEvery");
    return every instanceof Number && SWAP_CHOICES.indexOf(every) >= 0 ? every : SWAP_DEFAULT;
}

function swapLabel(every as Number) as String {
    return SWAP_LABELS[SWAP_CHOICES.indexOf(every)];
}

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
        Menu2.initialize({:title => "Doggos"});
        addItem(new WatchUi.MenuItem("Swap dogs", swapLabel(swapEvery()), :swap, null));
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
        } else if (item.getId() == :swap) {
            var menu = new WatchUi.Menu2({:title => "Swap dogs"});
            for (var i = 0; i < SWAP_CHOICES.size(); i++) {
                menu.addItem(new WatchUi.MenuItem(SWAP_LABELS[i], null, SWAP_CHOICES[i], null));
            }
            menu.setFocus(SWAP_CHOICES.indexOf(swapEvery()));
            WatchUi.pushView(menu, new SwapDelegate(item), WatchUi.SLIDE_LEFT);
        }
    }
}

// Picks how often the dogs swap, and shows it on the settings menu's item
class SwapDelegate extends WatchUi.Menu2InputDelegate {

    private var _item as MenuItem;

    function initialize(item as MenuItem) {
        Menu2InputDelegate.initialize();
        _item = item;
    }

    function onSelect(item as MenuItem) as Void {
        var every = item.getId() as Number;
        Storage.setValue("swapEvery", every);
        _item.setSubLabel(swapLabel(every));
        WatchUi.popView(WatchUi.SLIDE_RIGHT);
    }
}
