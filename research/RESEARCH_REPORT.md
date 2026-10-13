# Public VOCALOID lyric PV motion research

Research date: 2026-09-24. Status: discovery and generic code-mechanism inventory; PV motion remains uninspected.

## What the current evidence supports

Two public Bilibili searches returned 39 rows each: [VOCALOID PV / lyric motion](https://search.bilibili.com/all?keyword=VOCALOID%20PV%20%E5%AD%97%E5%B9%95%E5%8A%A8%E7%94%BB%20%E5%88%B6%E4%BD%9C%E6%95%99%E7%A8%8B) and [AE lyric-PV tutorials](https://search.bilibili.com/all?keyword=AE%20%E6%96%87%E5%AD%97PV%E6%95%99%E7%A8%8B%20%E6%AD%8C%E8%AF%8D%E5%8A%A8%E7%94%BB). After deduplicating by video ID, the register contains 76 distinct videos (`video_discovery.jsonl`). Six individual video pages returned HTTP 200 and supplied page metadata. Four more candidates in the corpus are linked only through their search results. Two cover images were opened and visually checked; covers show still images, not timed video frames. No video interval has been frame-inspected or motion-verified.

The corpus now has 42 records: 32 source-inspected generic code forms and 10 video metadata-only candidates. The 32 records describe code behavior in three public npm packages: 21 selected text routines from [usetypoui 1.0.1](https://www.npmjs.com/package/usetypoui/v/1.0.1), nine scene transitions from [Remotion Transitions 4.0.527](https://www.npmjs.com/package/@remotion/transitions/v/4.0.527), and two preset families from [Pyreon Kinetic Presets 0.51.0](https://www.npmjs.com/package/@pyreon/kinetic-presets/v/0.51.0). These are reusable code mechanisms, not effects observed in VOCALOID PVs. The Remotion package is marked UNLICENSED; this inventory records behavior and source references, not permission to reuse its code.

| Evidence stage | Count | What it means |
|---|---:|---|
| Distinct discovered video IDs | 76 | Deduplicated from two search result pages; titles and IDs only |
| Metadata-only video candidates in corpus | 10 | Six page metadata records and four search-result-only records |
| Cover images visually checked | 2 | Still-image inspection only |
| Frame-inspected segments | 0 | No timestamped video frames reviewed |
| Motion-verified segments | 0 | No temporal comparison or continuous interval reviewed |
| Source-inspected generic code forms | 32 | Behaviors read in published package source |
| Form-verified or reviewed samples | 0 | No independent review or PV-specific verification |

The candidate titled `【4K 60帧】初音未来的消失MV 中日双语版` appears in the search register, but that does not establish that it is the PV version the user meant. The identity of 命嫌 and the intended PV version remain unresolved. Named artists and titles remain aesthetic examples, not corpus filters.

## Access and source limits

The acquisition ledger has 38 attempts: 27 HTTP 200 responses, one HTTP 403, two HTTP 301 responses, seven connection-level `URLError` failures, and one `TimeoutError`. Redirects were not followed automatically. The Bilibili search pages and metadata pages were accessible; two cover images were cached. The [VocaDB API](https://vocadb.net/api/songs?query=Tell%20Your%20World&fields=WebLinks,PVs&maxResults=3) returned 403. The [YouTube oEmbed](https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DPqJNc9KVIZE&format=json) and [thumbnail](https://i.ytimg.com/vi/PqJNc9KVIZE/hqdefault.jpg) requests, [Niconico search](https://www.nicovideo.jp/search/VOCALOID%20PV%E4%BD%9C%E3%82%8A%E6%96%B9?sort=f&order=d), a [GitHub raw README](https://raw.githubusercontent.com/remotion-dev/remotion/main/README.md), a Motion Canvas package tarball, and the `动词打次` demo JavaScript bundle failed at the connection level or timed out. The demo's [public HTML root](https://std4453.github.io/dcdc/) returned 200, but its capability statements remain unverified because the bundle could not be read.

No player stream was extracted and no access code or external file linked from a video description was used. The video cache holds only search/page metadata and two still covers. The two cover checks do not support claims about motion, timing, lyrics, audio synchronization, or transitions.

## Visual categories to test later

These remain annotation prompts, not findings about the named references or the discovered candidates:

1. **Typography as the animated object:** character timing, baseline and tracking changes, scale punches, matte reveals, fragmentation, and interaction with graphic objects.
2. **Layered composition and framing:** type, image, graphic field, and background; overlaps, occlusion, parallax, reframing, and camera movement.
3. **Motif changes:** what repeats, and whether its scale, crop, color, orientation, count, or relation to the lyric changes over time.
4. **Panels and collage:** splits, insets, grids, texture, shuttering, and text crossing panel boundaries.
5. **Transition behavior:** trigger, mechanism, direction, duration, and the property carried across a cut. Beat or syllable synchronization requires accessible video and audio evidence.

Record sparse passages and counterexamples as well as dense motion. Keep uncertain labels unknown. Do not infer 3D construction or musical synchronization from a still or a package name.

## Reproduction and next work

`acquisition.jsonl` records URL, retrieval time, status, response size, hash, cache path, and failure where available. Cached bodies are content-addressed in `cache/`; the two Bilibili search results and individual page metadata are reproduced in `video_discovery.jsonl` and `corpus.jsonl`. `scripts/validate_corpus.py` currently reports 42 rows and zero errors. The initial corpus builder refuses to run on a non-empty corpus, so do not rerun it as an append operation.

The 3,000–5,000 distinct-form target has not been met. It requires a much larger reviewed sample and, for VOCALOID-specific findings, accessible timed video evidence. Next, continue bounded public-source discovery and seek lawful public frame or preview evidence; do not retry failed routes blindly. Expand source-code mechanisms only after checking overlap with `mechanics/mechanics.md`. Preserve the present access failures and keep source-inspected generic forms separate from observed PV forms.

Existing discovery and acquisition counts describe reconnaissance, not a representative sample. No frequency, prevalence, or style conclusion about VOCALOID PVs follows from them.
