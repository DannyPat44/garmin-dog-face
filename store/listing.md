# Connect IQ Store listing

Upload `bin/Doggos.iq` (from `make package`) at https://apps-developer.garmin.com
with the images in this folder (sizes from Garmin's brand guidelines):

- `cover.png`: 500x500 cover image / store icon (under 300 KB)
- `icon_128.png`: 128x128 on-device icon, full colour (AMOLED watches)
- `icon_128_64colors.png`: 128x128 on-device icon in Garmin's 64-colour palette (memory-in-pixel watches)
- `hero.png`: 1440x720 hero image (under 2 MB)
- `screenshot_*.png`: 416x416 screen images, one per dog and mood (under 150 KB each)

`make media` regenerates the screenshots, hero and cover from the renders; the
icons are made by hand.

The 60x60 launcher icon is built into the app.

## App name
Doggos

## Category
Watch Faces

## Short description
Three fluffy 3D pups take turns keeping you company.

## Description
Meet Millie, Nova and Ozzie: three fluffy, animated 3D dogs who take turns on your wrist.

- The dogs take turns, picked at random: Millie the tri-colour hound pup in her captain's hat, Nova the golden long-haired dachshund in her rainbow sombrero, and Ozzie the red cattle dog with her tennis ball.
- Each swap is a little scene: the dog on screen gets up and trots off the edge of the screen, and the next one trots in, turns to face you and sits. Ozzie brings her ball.
- Choose how often they swap (every time you look, every 5, 15 or 30 minutes, or every hour) and which dogs take turns, in the watch face's Customize menu.
- Each dog's mood follows your day: awake and curious, happy once you've hit your step goal, and curled up asleep from 10pm to 6am, lying down with a yawn at bedtime.
- A big, easy-to-read clock, with the date, battery percentage, steps and heart rate.
- Battery-friendly: the dogs only animate while the screen is fully on. Always-on mode shows a dim clock that moves slightly to protect your AMOLED screen.

Made for the Forerunner 265, 255 and 255 Music.

Want your own dog on your watch? Every dog is modelled in code and rendered with Blender. The tools and source are at https://github.com/DannyPat44/garmin-dog-face

## What's new (version 1.0)
First release: three dogs, three moods each, walking in and out on the hour or as often as you like.

## Permissions
None.

## Credits
Clock font: Fredoka, SIL Open Font License.
