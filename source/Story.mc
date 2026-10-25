import Toybox.Lang;

//! What the dogs do, as a queue of clips, decided each time the screen wakes:
//! - on the hour, the dog on screen walks out (picking up her ball, if she has
//!   one) and the next dog walks in and sits
//! - at bedtime the dog on screen lies down and stays the night: no swaps
//!   until morning, when she gets up
//! - between, she sits in a loop for her mood (awake or happy; happy and
//!   awake share the sitting pose, so they swap without a clip)
//! Plain logic with no device APIs, so it can be tested.
class Story {
    // Clips per dog, in the order tools/build_art.sh generates them; the
    // first three are the mood loops
    static const AWAKE = 0;
    static const HAPPY = 1;
    static const SLEEPY = 2;
    static const WALK_IN = 3;
    static const WALK_OUT = 4;
    static const LIE_DOWN = 5;
    static const GET_UP = 6;

    private var _dog as Number;
    private var _mood as Number;
    private var _hour as Number;
    // [dog, clip] pairs still to play before the mood loop
    private var _queue as Array<[Number, Number]> = [] as Array<[Number, Number]>;

    //! A fresh face: the dog walks in, and lies down if it's bedtime
    public function initialize(dog as Number, mood as Number, hour as Number) {
        _dog = dog;
        _mood = mood;
        _hour = hour;
        _queue.add([dog, WALK_IN]);
        if (mood == SLEEPY) {
            _queue.add([dog, LIE_DOWN]);
        }
    }

    //! The screen woke at `hour` with the dogs' mood now `mood`; `nextDog` is
    //! who takes over if it's time to swap.
    public function update(hour as Number, mood as Number, nextDog as Number) as Void {
        var newHour = hour != _hour;
        _hour = hour;
        if (mood == SLEEPY) {
            if (_mood != SLEEPY) {
                _queue.add([_dog, LIE_DOWN]);
            }
            _mood = mood;
            return;
        }
        if (_mood == SLEEPY) {
            _queue.add([_dog, GET_UP]);
        }
        _mood = mood;
        if (newHour && nextDog != _dog) {
            _queue.add([_dog, WALK_OUT]);
            _queue.add([nextDog, WALK_IN]);
            _dog = nextDog;
        }
    }

    //! The next clip to play as [dog, clip]: the queue, then the mood loop
    public function next() as [Number, Number] {
        if (_queue.size() > 0) {
            var clip = _queue[0];
            _queue = _queue.slice(1, null);
            return clip;
        }
        return [_dog, _mood];
    }

    //! The screen went off mid-story: skip to how it ends
    public function skip() as Void {
        _queue = [] as Array<[Number, Number]>;
    }

    public function isTelling() as Boolean {
        return _queue.size() > 0;
    }

    public function dog() as Number {
        return _dog;
    }

    public function mood() as Number {
        return _mood;
    }

    //! The mood still matching a clip's last frame, drawn under the clip so
    //! there's no gap before the next one; null when she ends off screen.
    //! Walk-ins and getting up end on the awake loop's first frame.
    static function endStill(clip as Number) as Number? {
        if (clip == WALK_OUT) {
            return null;
        } else if (clip == WALK_IN || clip == GET_UP) {
            return AWAKE;
        } else if (clip == LIE_DOWN) {
            return SLEEPY;
        }
        return clip;
    }
}
