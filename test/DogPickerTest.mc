import Toybox.Lang;
import Toybox.Test;

(:test)
function pickerAllowsTheDogsSwitchedOn(logger as Logger) as Boolean {
    var allowed = DogPicker.allowed([true, false, true]);
    Test.assertEqual(allowed.size(), 2);
    Test.assertEqual(allowed[0], 0);
    Test.assertEqual(allowed[1], 2);
    return true;
}

(:test)
function pickerAllowsEveryDogWhenAllAreOff(logger as Logger) as Boolean {
    Test.assertEqual(DogPicker.allowed([false, false, false]).size(), 3);
    return true;
}

(:test)
function pickerNeverPicksADogSwitchedOff(logger as Logger) as Boolean {
    for (var roll = 0; roll < 6; roll++) {
        Test.assertEqual(DogPicker.next([false, true, false], null, roll), 1);
        Test.assert(DogPicker.next([true, false, true], 1, roll) != 1);
    }
    return true;
}

(:test)
function pickerPicksSomeoneElseWhenItCan(logger as Logger) as Boolean {
    for (var roll = 0; roll < 6; roll++) {
        Test.assertEqual(DogPicker.next([true, true, false], 0, roll), 1);
    }
    // With only her switched on, she stays
    Test.assertEqual(DogPicker.next([false, false, true], 2, 5), 2);
    return true;
}

(:test)
function pickerKnowsWhoIsStillAllowed(logger as Logger) as Boolean {
    Test.assert(DogPicker.isAllowed([true, false, true], 2));
    Test.assert(!DogPicker.isAllowed([true, false, true], 1));
    Test.assert(DogPicker.isAllowed([false, false, false], 1));
    return true;
}
