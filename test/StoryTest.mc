import Toybox.Lang;
import Toybox.Test;

// Plays out everything queued, returning the clips as [dog, clip] pairs
function storyClips(story as Story) as Array<[Number, Number]> {
    var clips = [] as Array<[Number, Number]>;
    while (story.isTelling()) {
        clips.add(story.next());
    }
    return clips;
}

function sameClips(actual as Array<[Number, Number]>, expected as Array<[Number, Number]>) as Boolean {
    if (actual.size() != expected.size()) {
        return false;
    }
    for (var i = 0; i < actual.size(); i++) {
        if (actual[i][0] != expected[i][0] || actual[i][1] != expected[i][1]) {
            return false;
        }
    }
    return true;
}

(:test)
function storyStartsWithAWalkIn(logger as Logger) as Boolean {
    var story = new Story(1, Story.AWAKE, 9);
    Test.assert(sameClips(storyClips(story), [[1, Story.WALK_IN]]));
    // Then her mood loop, over and over
    Test.assert(sameClips([story.next(), story.next()], [[1, Story.AWAKE], [1, Story.AWAKE]]));
    return true;
}

(:test)
function storyStartsAtBedtimeLyingDown(logger as Logger) as Boolean {
    var story = new Story(0, Story.SLEEPY, 23);
    Test.assert(sameClips(storyClips(story), [[0, Story.WALK_IN], [0, Story.LIE_DOWN]]));
    Test.assert(sameClips([story.next()], [[0, Story.SLEEPY]]));
    return true;
}

(:test)
function storySwapsDogsOnTheHour(logger as Logger) as Boolean {
    var story = new Story(0, Story.AWAKE, 9);
    storyClips(story);
    story.update(9, Story.AWAKE, 2);
    Test.assert(!story.isTelling());
    story.update(10, Story.AWAKE, 2);
    Test.assert(sameClips(storyClips(story), [[0, Story.WALK_OUT], [2, Story.WALK_IN]]));
    Test.assertEqual(story.dog(), 2);
    return true;
}

(:test)
function storyChangesMoodWithoutAClip(logger as Logger) as Boolean {
    var story = new Story(1, Story.AWAKE, 9);
    storyClips(story);
    story.update(9, Story.HAPPY, 0);
    Test.assert(!story.isTelling());
    Test.assert(sameClips([story.next()], [[1, Story.HAPPY]]));
    return true;
}

(:test)
function storyStaysTheNight(logger as Logger) as Boolean {
    var story = new Story(1, Story.AWAKE, 21);
    storyClips(story);
    story.update(22, Story.SLEEPY, 2);
    Test.assert(sameClips(storyClips(story), [[1, Story.LIE_DOWN]]));
    // No swaps overnight
    story.update(1, Story.SLEEPY, 0);
    story.update(3, Story.SLEEPY, 2);
    Test.assert(!story.isTelling());
    Test.assertEqual(story.dog(), 1);
    // Morning: she gets up, then hands over
    story.update(6, Story.AWAKE, 0);
    Test.assert(sameClips(storyClips(story), [[1, Story.GET_UP], [1, Story.WALK_OUT], [0, Story.WALK_IN]]));
    Test.assert(sameClips([story.next()], [[0, Story.AWAKE]]));
    return true;
}

(:test)
function storySkipsToTheEndWhenTheScreenGoesOff(logger as Logger) as Boolean {
    var story = new Story(0, Story.AWAKE, 9);
    storyClips(story);
    story.update(10, Story.HAPPY, 1);
    story.next();
    story.skip();
    Test.assert(!story.isTelling());
    Test.assert(sameClips([story.next()], [[1, Story.HAPPY]]));
    return true;
}

(:test)
function storyEndStills(logger as Logger) as Boolean {
    Test.assert(Story.endStill(Story.WALK_OUT) == null);
    Test.assertEqual(Story.endStill(Story.WALK_IN), Story.AWAKE);
    Test.assertEqual(Story.endStill(Story.GET_UP), Story.AWAKE);
    Test.assertEqual(Story.endStill(Story.LIE_DOWN), Story.SLEEPY);
    Test.assertEqual(Story.endStill(Story.HAPPY), Story.HAPPY);
    return true;
}

(:test)
function storyWalksFillTheScreen(logger as Logger) as Boolean {
    Test.assert(Story.fillsScreen(Story.WALK_IN));
    Test.assert(Story.fillsScreen(Story.WALK_OUT));
    Test.assert(!Story.fillsScreen(Story.AWAKE));
    Test.assert(!Story.fillsScreen(Story.LIE_DOWN));
    Test.assert(!Story.fillsScreen(Story.GET_UP));
    return true;
}

(:test)
function storySwapsADogSwitchedOffStraightAway(logger as Logger) as Boolean {
    var story = new Story(0, Story.AWAKE, 9);
    storyClips(story);
    story.swapTo(2);
    Test.assert(sameClips(storyClips(story), [[0, Story.WALK_OUT], [2, Story.WALK_IN]]));
    // The same hour, so no second swap
    story.update(9, Story.AWAKE, 2);
    Test.assert(!story.isTelling());
    return true;
}

(:test)
function storyLeavesASleepingDogSwitchedOffUntilMorning(logger as Logger) as Boolean {
    var story = new Story(0, Story.SLEEPY, 23);
    storyClips(story);
    story.swapTo(1);
    Test.assert(!story.isTelling());
    Test.assertEqual(story.dog(), 0);
    story.update(6, Story.AWAKE, 1);
    Test.assert(sameClips(storyClips(story), [[0, Story.GET_UP], [0, Story.WALK_OUT], [1, Story.WALK_IN]]));
    return true;
}
