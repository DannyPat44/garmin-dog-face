import Toybox.Lang;
import Toybox.Test;

function sameBox(actual as [Number, Number, Number, Number], expected as [Number, Number, Number, Number]) as Boolean {
    for (var i = 0; i < 4; i++) {
        if (actual[i] != expected[i]) {
            return false;
        }
    }
    return true;
}

(:test)
function layoutBoxOnTheFr265(logger as Logger) as Boolean {
    // Where the renders are framed (DOG_AT and CROP in dog_rig.py)
    Test.assert(sameBox(DogLayout.box(416), [97, 134, 222, 249]));
    return true;
}

(:test)
function layoutBoxScalesToTheFr255(logger as Logger) as Boolean {
    // The size tools/build_art.sh makes the 260px art
    Test.assert(sameBox(DogLayout.box(260), [60, 84, 139, 156]));
    return true;
}
