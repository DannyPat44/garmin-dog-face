import Toybox.Lang;

//! What the dogs do, as a queue of clips, decided each time the screen wakes:
//! - each time slot (an hour, or as often as the settings say; see slot()),
//!   the dog on screen walks out (picking up her ball, if she has one) and
//!   the next dog walks in and sits
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
    private var _slot as Number;
    // [dog, clip] pairs still to play before the mood loop
    private var _queue as Array<[Number, Number]> = [] as Array<[Number, Number]>;
    // The clip last handed out by next(), which may still be playing
    private var _current as [Number, Number]? = null;

    //! A fresh face: the dog walks in, and lies down if it's bedtime
    public function initialize(dog as Number, mood as Number, slot as Number) {
        _dog = dog;
        _mood = mood;
        _slot = slot;
        _queue.add([dog, WALK_IN]);
        if (mood == SLEEPY) {
            _queue.add([dog, LIE_DOWN]);
        }
    }

    //! The screen woke in time slot `slot` with the dogs' mood now `mood`;
    //! `nextDog` is who takes over if it's time to swap.
    public function update(slot as Number, mood as Number, nextDog as Number) as Void {
        var newSlot = slot != _slot;
        _slot = slot;
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
        if (newSlot && nextDog != _dog) {
            swap(nextDog);
        }
    }

    //! The dogs on the watch changed and she's no longer one of them: she
    //! walks out and `dog` walks in, unless she's asleep (the morning
    //! handover swaps her then)
    public function swapTo(dog as Number) as Void {
        if (_mood == SLEEPY || dog == _dog) {
            return;
        }
        swap(dog);
    }

    //! She walks out and `dog` walks in; if she's still waiting to walk in,
    //! she was never seen, so `dog` walks in instead
    private function swap(dog as Number) as Void {
        if (_queue.size() == 1 && _queue[0][0] == _dog && _queue[0][1] == WALK_IN) {
            _queue = [[dog, WALK_IN]] as Array<[Number, Number]>;
        } else {
            _queue.add([_dog, WALK_OUT]);
            _queue.add([dog, WALK_IN]);
        }
        _dog = dog;
    }

    //! The next clip to play as [dog, clip]: the queue, then the mood loop
    public function next() as [Number, Number] {
        var clip = [_dog, _mood] as [Number, Number];
        if (_queue.size() > 0) {
            clip = _queue[0];
            _queue = _queue.slice(1, null);
        }
        _current = clip;
        return clip;
    }

    //! The screen went off mid-story: skip to how it ends, except that the
    //! new dog's walk-in (the part worth seeing) waits for the next look,
    //! from the start if it was cut off, followed by lying down at bedtime
    public function skip() as Void {
        var walkIn = _current != null && _current[0] == _dog && _current[1] == WALK_IN;
        for (var i = 0; i < _queue.size(); i++) {
            if (_queue[i][0] == _dog && _queue[i][1] == WALK_IN) {
                walkIn = true;
            }
        }
        _queue = [] as Array<[Number, Number]>;
        _current = null;
        if (walkIn) {
            _queue.add([_dog, WALK_IN]);
            if (_mood == SLEEPY) {
                _queue.add([_dog, LIE_DOWN]);
            }
        }
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

    //! The time slot dogs swap in: minutes since midnight divided by `every`
    //! minutes, or with `every` 0, `looks` (a count of the times the screen
    //! woke), so they swap every time you look
    static function slot(minutes as Number, every as Number, looks as Number) as Number {
        return every > 0 ? minutes / every : looks;
    }

    //! Walks fill the whole screen, so she comes and goes off its edge; the
    //! other clips fill the dog's box
    static function fillsScreen(clip as Number) as Boolean {
        return clip == WALK_IN || clip == WALK_OUT;
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
