import Toybox.Lang;

//! Where the dog's box goes on a round screen of any size. The face is laid
//! out for the FR265's 416px screen and scaled to others; tools/build_art.sh
//! scales the art the same way, and tools/blender/dog_rig.py (DOG_AT) frames
//! the walks around the box. Plain logic, so it can be tested.
class DogLayout {
    static const DESIGN_SCREEN = 416;

    //! A size on the 416px screen, scaled to `screen`
    static function scaled(px as Number, screen as Number) as Number {
        return (px * screen / DESIGN_SCREEN.toFloat() + 0.5).toNumber();
    }

    //! The box the loops and stills are cropped to, as [x, y, width, height]
    static function box(screen as Number) as [Number, Number, Number, Number] {
        var width = scaled(222, screen);
        return [(screen - width) / 2, scaled(134, screen), width, scaled(249, screen)];
    }
}
