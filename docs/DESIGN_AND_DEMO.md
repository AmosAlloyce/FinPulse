# Interactive workspace and recorded demonstration

The web workspace uses the original Python event contracts, synthetic generator, quality rules, dimensional loader and SQL marts. Its six sections expose these actual operations through a React interface. The public runtime has a 512 MB container budget; Kafka, Spark and Airflow remain separate deployment options in the original project, not services claimed to run inside the public sandbox.

The visual direction follows Scroll Craft's live-surface grammar. The new opening retains one delivered event ID while the visitor switches between source, quality and published output, and opens that event's real immutable envelope. Background and document edge move subtly in natural scroll; controls and text remain stable. Each visitor's actions are isolated, and scrolling never approves or modifies a record.

DM Sans is self-hosted with its license. Body text is 16px, the new trace uses explicit focus states, and phone layouts stack the document beneath its introduction. Reduced motion removes positional effects. No generated imagery or external image API is required. The application captures used on Alloyce's portfolio come from the running workspace.

## Narrated demo

`web/public/demo/finpulse-demo.mp4` is a recording of actual browser interactions, synchronized to a 113.22-second neural narration. Groq Orpheus English, built-in Troy voice, supplies the AI-generated speech. English captions are available as a WebVTT track and embedded subtitles. Playback is opt-in; there is no autoplaying audio.

The recorder at `web/scripts/record-demo.mjs` expects `NARRATION_PREFIX` to point to matching `.wav`, `.json` and `.vtt` files. The shared voice-production scripts and narration text are in the [PeopleOS portfolio repository](https://github.com/AmosAlloyce/peopleos/blob/main/docs/NARRATION.md). The JSON contains measured `chapters` with `id`, `start`, `duration` and `end`; the recording follows those times without stretching the voice into fixed slots. No provider key is embedded in the video or frontend.

```bash
cd web
BROWSER_PATH=/path/to/chromium NARRATION_PREFIX=/path/to/finpulse-neural npm run record:demo
```

## Verification

The browser integration test exercises all six sections, four input scenarios, pipeline execution, correction approval, duplicate suppression, late-event warnings, product schemas, CSV export, independent visitors, keyboard navigation and reset. It checks layouts at 1440, 1024, 768, 390 and 320px. The added trace controls preserve the selected event while changing the explanation and open its real envelope.

`web/scripts/scroll-review.mjs` produced 24 rendered samples across desktop, 390px phone, 360×640 compact phone and reduced-motion views. The screenshot sheets were inspected; there was no horizontal page overflow or runtime error. These are headless-browser checks, not a real iPhone test or a subjective listening assessment.

Backend verification: 27 tests passed, branch-aware coverage 88.59% against the repository's 75% threshold; Ruff lint and formatting checks passed. Current media and deployment results are recorded after final packaging in the portfolio handoff documentation.
