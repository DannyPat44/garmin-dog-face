# Connect IQ Store listing

Everything the store listing uses, and how to publish a new version.

- Listing: https://apps.garmin.com/apps/af36c22b-b7f3-4321-97c3-78ec36b56ff0 (Doggo Crew Face)
- Developer dashboard: https://apps.garmin.com/developer/dashboard (sign in with the Garmin account)
- Preview video: https://www.youtube.com/watch?v=q-ZICw2ZBQc (`docs/media/nova_hour.mp4`)

## Assets in this folder

Sizes from Garmin's brand guidelines.

| File | Store field | Made with |
|---|---|---|
| `cover.png` | Cover image, 500x500, under 300 KB | `make media` |
| `hero.png` | Hero image, 1440x720, under 2 MB | `make media` |
| `screenshot_*.png` | Screen images, 416x416, under 150 KB each; the store takes 5 | `make media` |
| `icon_128.png` | On-device icon, full colour (AMOLED watches) | `make icons` |
| `icon_128_64colors.png` | On-device icon in Garmin's 64-colour palette (memory-in-pixel watches) | `make icons` |

The five screenshots on the listing: `screenshot_millie`, `_nova`, `_ozzie`,
`_millie_happy` and `_millie_sleepy`. The 60x60 launcher icon is built into
the app.

`make media` and `make icons` work from the renders in `build/frames/rig/`;
render the dogs first (`make rig`) if those are missing or out of date.

## Listing text

**Title:** Doggo Crew Face (the app itself is named Doggos on the watch)

**Tagline:** Three animated dogs take turns on your wrist, around a clear, readable face.

**Description:**

```
A watch face that makes you smile every time you check it, and still reads at a glance.

Three dogs take turns on your wrist. When it's time to swap, the dog on screen trots off the edge and the next one trots in, turns to face you and sits down. The clock and stats are always drawn on top, so the dog never hides the time.

Meet the crew:
- Millie, a tri-colour hound pup in a little captain's hat
- Nova, a golden long-haired dachshund in a straw sombrero with a rainbow band
- Ozzie, a red cattle dog mix who brings her tennis ball

Their moods follow your day: head tilts and tail wags most of the time, tongue-out happy once you reach your step goal, and at 10pm a yawn and a lie-down for the night.

What you get:
- A big, easy-to-read clock, with the date, battery percentage, steps and heart rate
- Choose which dogs take turns, and how often: every time you raise your wrist, every 5, 15 or 30 minutes, or every hour
- Easy on the battery: the dogs only move while the screen is fully on, and always-on mode on the Forerunner 265 shows a dim, shifting clock to protect the AMOLED screen

For the Forerunner 265, 255 and 255 Music.

Free. Every dog is modelled in code and rendered in Blender; if you're comfortable with code, the source and tools let you put your own dog on your watch: https://github.com/DannyPat44/garmin-dog-face
```

The description should sell the face before it lists features: why a dog
lover would want it first, then a short summary of what it does. Keep the
watch list in step with `manifest.xml`.

**What's New (1.0):** Version 1.0: now on the Forerunner 255 and 255 Music.
Choose which dogs take turns and how often they swap. Millie has a captain's
hat, and the dogs trot in and out across the whole screen, turning naturally
as they go.

## Other answers on the form

| Question | Answer |
|---|---|
| Category | Animal (no subcategory) |
| Collects user data | No |
| ANT+ profiles, regional limits, monetization | No |
| Icons for the app store on the device | Yes (`icon_128*.png`) |
| Contact email (shown publicly) | doggos.watchface@proton.me |
| Source code URL | https://github.com/DannyPat44/garmin-dog-face |
| Review notifications | Yes |
| Let the store add newly compatible watches | Yes |

**Permissions:** none. **Credits:** clock font Fredoka, SIL Open Font License.

## Publishing a new version

1. Merge the changes to `main`, then `make test` and check the face on each
   watch in the simulator (`make run DEVICE=fr255`, and so on).
2. Build the package: `make package` (writes `bin/Doggos.iq`, about 14 MB;
   the Makefile gives the compiler the bigger Java heap it needs).
3. On the dashboard, open Doggo Crew Face and choose **Upload New Version**.
   Attach `bin/Doggos.iq` and give the version (the last was 1.0), then
   **Upload and publish**. (Claude in Chrome can only attach files under
   10 MB: split the package and join the parts in the page, or attach it by
   hand.)
4. On the next page (Update Details), write **What's New** for this version,
   and update the description, screenshots or video if the change calls for
   it (then update this file to match). **Submit**.
5. Garmin reviews it; the listing shows "Version update pending" until then.

A new preview video: `make media`, upload the clip to YouTube (not made for
kids, public), and put the link in the listing's Preview Video.

## Store quirks seen so far

- **On-device icons can't be replaced**: once 128x128 icons are submitted, new
  ones are refused ("There's an existing app icon..."), even after removing
  the old ones. The listing still has the first icons (Millie in her red
  collar); the new ones with her captain's hat are in this folder. Ask Garmin
  developer support to replace them.
- **Broken image previews** on the dashboard and the edit form: they load from
  `api.appstore.garmin.com`, which often doesn't return them. The public
  listing shows the images fine.
- **"Trouble communicating with our servers"** on Submit: the change may have
  saved anyway; reload the edit page and check before submitting again.
- **Another browser extension can cover the edit form** after a file is
  attached, blocking clicks; reloading the page clears it.
