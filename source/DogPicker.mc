import Toybox.Lang;

//! Which dogs take turns, from the watch face's settings, and who goes next.
//! Plain logic with no device APIs, so it can be tested.
class DogPicker {

    //! The dogs switched on, by index; all of them if every one is off, so
    //! the face is never empty
    static function allowed(shown as Array<Boolean>) as Array<Number> {
        var dogs = [] as Array<Number>;
        for (var i = 0; i < shown.size(); i++) {
            if (shown[i]) {
                dogs.add(i);
            }
        }
        if (dogs.size() == 0) {
            for (var i = 0; i < shown.size(); i++) {
                dogs.add(i);
            }
        }
        return dogs;
    }

    //! A dog that's switched on, other than `current` when there's a choice;
    //! `roll` is any random number
    static function next(shown as Array<Boolean>, current as Number?, roll as Number) as Number {
        var dogs = allowed(shown);
        if (current != null && dogs.size() > 1) {
            dogs.remove(current);
        }
        return dogs[roll.abs() % dogs.size()];
    }

    //! Whether `dog` is still one of the dogs taking turns
    static function isAllowed(shown as Array<Boolean>, dog as Number) as Boolean {
        return allowed(shown).indexOf(dog) >= 0;
    }
}
