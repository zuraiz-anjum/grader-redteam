# How models cheat graders, and how to build graders that hold

I build evaluation environments for frontier models. An evaluation has three parts: a task, a sandbox, and a grader that decides whether the model did the job. The task gets most of the attention. The grader is where a lot of the bugs are.

A capable model under optimisation pressure will find the cheapest path to a high score, and the cheapest path is often not the one the designer meant. This is not new. DeepMind keeps a long public list of specification gaming examples from reinforcement learning, from a boat racing agent circling for points to simulated robots exploiting physics bugs (Krakovna et al., 2020). Amodei et al. (2016) named the general problem reward hacking. What changed is that today's models can read files, run shell commands and write code, so the exploits look like ordinary software work.

Public reports say the same thing. METR wrote in 2025 that recent frontier models were reward hacking on its tasks, including modifying tests or scoring code and finding the answers used to check their work. OpenAI's paper on monitoring reasoning models (Baker et al., 2025) describes coding agents that made tests pass by editing the tests or exiting early instead of fixing the bug. Anthropic's Claude 3.7 Sonnet system card describes the model special-casing tests, returning expected values directly instead of writing a general solution. None of this needs malice. It is the grader paying out for the wrong thing.

Below are the patterns those sources document, why each gets past a naive grader, and the standard defence.

## Reading the answer from a reachable file

What it looks like: the expected output sits somewhere the model can read. A fixtures folder, a cached result, a reference solution left in the image, an old commit in the git history. The model finds it with one search and copies it.

Why it passes: the grader checks the output, and the output is correct. It was just not produced by solving anything.

The defence: the answer key never exists inside the sandbox in a form the candidate can read. Keep it outside the container, or readable only by a user the model does not run as. Better still, compute the expected value at grading time from data the candidate never saw. Then test it: act as the sandbox user and try to read every secret path. If you can, so can the model.

## Writing the reward or test result directly

What it looks like: the harness reads a score from a file such as `reward.json`. The model finds the file, or guesses the name, and writes a perfect score itself.

Why it passes: some graders only write the reward when the checks complete, or skip grading when a result already exists. Either way, the planted file survives.

The defence: the candidate must have no way to reach the place the score is written, during the run or after it. Write the reward from a separate grading process into a location outside the candidate's workspace, write it once at the end, write atomically, and refuse to follow a symlink when writing.

## Editing or deleting the tests

What it looks like: the tests ship in the workspace. The model changes the expected values, comments out the failing assertion, empties the test list, or exits before the tests run.

Why it passes: the grader trusts files the candidate was able to change.

The defence: grade with tests the candidate never had write access to. Copy only the deliverable into a clean grading environment, and treat an empty or skipped test run as a failure, not a pass.

## Faking success output

What it looks like: the grader decides success by reading printed output or a log. The model prints `ALL TESTS PASSED`.

Why it passes: text claiming success is cheap, and the grader took the claim at face value.

The defence: grade by value, never by message. Run the candidate's code in a separate process, feed it inputs it has not seen, and compare the outputs yourself. Compute the expected answers in the grading process, collect the candidate's return values as data, and discard its printed output, so nothing it prints can decide the score.

## Hardcoding the visible test cases

What it looks like: the task ships a few example inputs and outputs. The model writes a lookup table for exactly those inputs and returns something plausible for the rest.

Why it passes: the grader runs the same visible cases. A lookup table and a real solution look identical on them.

The defence: the visible examples are for the model. The grade comes from held-out cases it never sees, ideally generated fresh at grading time. Write the lookup table yourself as a negative control and check that it scores zero.

## Hanging or crashing the grader

What it looks like: the submission loops forever, or is malformed in a way that makes the grader throw. If a crashed grader leaves no reward, the harness may fall back to an old or planted one.

Why it passes: the grader assumed the submission would behave.

The defence: run the submission under a timeout in its own process, catch every failure, and write a zero for it. Treat a missing reward as a broken grader, not as a zero.

## Malformed submissions and path escapes

What it looks like: binary junk instead of text, an enormous file, or a deliverable that is a symlink pointing at the answer key or at a file outside the output directory.

Why it passes: the grader followed the link or decoded the bytes without checking.

The defence: refuse symlinks, cap the size, require valid text, and resolve every path against the output directory before opening it.

## Habits that cover most of this

Grade in a separate process, ideally a separate container, that receives only the deliverable.

Grade by value on held-out data, not on log lines or the examples the model can see.

Keep the answer key and the reward file out of the candidate's reach.

Run a few controls on every change: a correct solution must score one, and an empty submission and a lookup table of the visible cases must score zero.

I wrote a small tool, grader-redteam, that runs the mechanical half of this against any grader that writes a reward file: empty submissions, planted rewards, symlinks, edited tests, fake success output, hangs and junk bytes. It does not replace thinking about the task, but it catches the obvious holes early.

## Checklist

- The answer key is unreadable by the sandbox user, or does not exist on disk.
- The reward is written by a separate grading process to a place the candidate cannot reach.
- The grader writes the reward once at the end, atomically, without following symlinks.
- Tests used for grading cannot be changed by the candidate.
- The submission runs in its own process with a timeout.
- Scores come from held-out cases compared by value.
- Nothing is graded on printed output or log text.
- Symlinks, oversized files and malformed input score zero without crashing the grader.
- The empty submission scores zero.
- A lookup table of the visible cases scores zero.

## Sources

- Victoria Krakovna, Jonathan Uesato, Vladimir Mikulik, Matthew Rahtz, Tom Everitt, Ramana Kumar, Zac Kenton, Jan Leike and Shane Legg, "Specification gaming: the flip side of AI ingenuity", DeepMind blog, April 2020.
- Dario Amodei, Chris Olah, Jacob Steinhardt, Paul Christiano, John Schulman and Dan Mané, "Concrete Problems in AI Safety", arXiv:1606.06565, 2016.
- Sydney Von Arx, Lawrence Chan and Beth Barnes, "Recent Frontier Models Are Reward Hacking", METR blog, June 2025.
- Bowen Baker et al., "Monitoring Reasoning Models for Misbehavior and the Risks of Promoting Obfuscation", OpenAI, arXiv:2503.11926, 2025.
- Anthropic, "Claude 3.7 Sonnet System Card", February 2025.
